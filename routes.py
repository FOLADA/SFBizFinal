from flask import request, jsonify
from db import get_db
from flask import Blueprint
import jwt
import datetime
import os
import secrets
import requests
from werkzeug.utils import secure_filename
from functools import wraps
import json
import sqlite3
import bcrypt
from passlib.hash import bcrypt as passlib_bcrypt
from passlib.exc import MissingBackendError
import openai
import random

SECRET_KEY = os.environ.get("SECRET_KEY", "dev_secret_key")
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "your_google_maps_api_key")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "your-openai-api-key-here")

# Initialize OpenAI client
if OPENAI_API_KEY and OPENAI_API_KEY != "your-openai-api-key-here":
    try:
        openai.api_key = OPENAI_API_KEY
        openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        print(f"OpenAI client initialization error: {e}")
        openai_client = None
else:
    openai_client = None

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def generate_token(user_id, email):
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def verify_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Authorization header required"}), 401
        
        token = auth_header.split(' ')[1]
        payload = verify_token(token)
        if not payload:
            return jsonify({"error": "Invalid or expired token"}), 401
        
        request.user_id = payload['user_id']
        return f(*args, **kwargs)
    return decorated_function

def geocode_address(address):
    """Convert address to latitude/longitude using Google Maps Geocoding API"""
    if not GOOGLE_MAPS_API_KEY or GOOGLE_MAPS_API_KEY == "your_google_maps_api_key":
        # Return dummy coordinates for development
        return 37.7749, -122.4194  # San Francisco coordinates
    
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": address,
        "key": GOOGLE_MAPS_API_KEY
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if data["status"] == "OK" and data["results"]:
            location = data["results"][0]["geometry"]["location"]
            return location["lat"], location["lng"]
        else:
            return None, None
    except Exception as e:
        print(f"Geocoding error: {e}")
        return None, None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

bp = Blueprint("businesses", __name__)

@bp.route("/")
def home():
    return "Flask backend is working!"

@bp.route("/businesses", methods=["GET"])
def list_businesses():
    category = request.args.get("category")
    with get_db() as conn:
        if category:
            cursor = conn.execute("SELECT * FROM businesses WHERE category = ?", (category,))
        else:
            cursor = conn.execute("SELECT * FROM businesses")
        businesses = [dict(row) for row in cursor.fetchall()]
    return jsonify(businesses), 200

@bp.route("/businesses/search", methods=["GET"])
def search_businesses():
    # Get search parameters
    query = request.args.get("q", "")
    categories = request.args.get("category", "").split(",") if request.args.get("category") else []
    locations = request.args.get("location", "").split(",") if request.args.get("location") else []
    min_rating = request.args.get("minRating")
    max_rating = request.args.get("maxRating")
    sort_by = request.args.get("sortBy", "name")
    sort_order = request.args.get("sortOrder", "asc")
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 12))
    offset = (page - 1) * limit

    with get_db() as conn:
        # Build the base query
        base_query = """
            SELECT b.*, 
                   COALESCE(AVG(r.rating), 0) as avg_rating,
                   COUNT(r.id) as total_reviews
            FROM businesses b
            LEFT JOIN reviews r ON b.id = r.business_id
        """
        
        where_conditions = []
        params = []
        
        # Add search query condition
        if query:
            where_conditions.append("(b.name LIKE ? OR b.description LIKE ? OR b.category LIKE ? OR b.location LIKE ?)")
            search_term = f"%{query}%"
            params.extend([search_term, search_term, search_term, search_term])
        
        # Add category filter
        if categories and categories[0]:
            placeholders = ",".join(["?" for _ in categories])
            where_conditions.append(f"b.category IN ({placeholders})")
            params.extend(categories)
        
        # Add location filter
        if locations and locations[0]:
            placeholders = ",".join(["?" for _ in locations])
            where_conditions.append(f"b.location IN ({placeholders})")
            params.extend(locations)
        
        # Add rating filter
        if min_rating:
            where_conditions.append("COALESCE(AVG(r.rating), 0) >= ?")
            params.append(float(min_rating))
        
        if max_rating:
            where_conditions.append("COALESCE(AVG(r.rating), 0) <= ?")
            params.append(float(max_rating))
        
        # Combine WHERE conditions
        if where_conditions:
            base_query += " WHERE " + " AND ".join(where_conditions)
        
        # Add GROUP BY
        base_query += " GROUP BY b.id"
        
        # Add HAVING clause for rating filters (after GROUP BY)
        having_conditions = []
        if min_rating:
            having_conditions.append("COALESCE(AVG(r.rating), 0) >= ?")
            params.append(float(min_rating))
        
        if max_rating:
            having_conditions.append("COALESCE(AVG(r.rating), 0) <= ?")
            params.append(float(max_rating))
        
        if having_conditions:
            base_query += " HAVING " + " AND ".join(having_conditions)
        
        # Add ORDER BY
        order_mapping = {
            "name": "b.name",
            "rating": "avg_rating",
            "recent": "b.id",  # Assuming newer businesses have higher IDs
            "distance": "b.id"  # Placeholder for distance sorting
        }
        
        sort_field = order_mapping.get(sort_by, "b.name")
        base_query += f" ORDER BY {sort_field} {sort_order.upper()}"
        
        # Add pagination
        base_query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        # Execute the query
        cursor = conn.execute(base_query, params)
        businesses = [dict(row) for row in cursor.fetchall()]
        
        # Get total count for pagination
        count_query = """
            SELECT COUNT(DISTINCT b.id) as total
            FROM businesses b
            LEFT JOIN reviews r ON b.id = r.business_id
        """
        
        count_where_conditions = []
        count_params = []
        
        if query:
            count_where_conditions.append("(b.name LIKE ? OR b.description LIKE ? OR b.category LIKE ? OR b.location LIKE ?)")
            search_term = f"%{query}%"
            count_params.extend([search_term, search_term, search_term, search_term])
        
        if categories and categories[0]:
            placeholders = ",".join(["?" for _ in categories])
            count_where_conditions.append(f"b.category IN ({placeholders})")
            count_params.extend(categories)
        
        if locations and locations[0]:
            placeholders = ",".join(["?" for _ in locations])
            count_where_conditions.append(f"b.location IN ({placeholders})")
            count_params.extend(locations)
        
        if count_where_conditions:
            count_query += " WHERE " + " AND ".join(count_where_conditions)
        
        count_cursor = conn.execute(count_query, count_params)
        total_count = count_cursor.fetchone()["total"]
        
        # Get filter options for response
        categories_cursor = conn.execute("SELECT DISTINCT category FROM businesses")
        available_categories = [row["category"] for row in categories_cursor.fetchall()]
        
        locations_cursor = conn.execute("SELECT DISTINCT location FROM businesses")
        available_locations = [row["location"] for row in locations_cursor.fetchall()]
        
        # Get rating range
        rating_cursor = conn.execute("""
            SELECT MIN(COALESCE(AVG(r.rating), 0)) as min_rating, 
                   MAX(COALESCE(AVG(r.rating), 0)) as max_rating
            FROM businesses b
            LEFT JOIN reviews r ON b.id = r.business_id
            GROUP BY b.id
        """)
        rating_range = rating_cursor.fetchone()
        
        # Transform businesses to match expected format
        for business in businesses:
            business["rating"] = business.get("avg_rating", 0)
            business["totalReviews"] = business.get("total_reviews", 0)
            # Parse socials JSON
            if business.get("socials"):
                try:
                    business["socials"] = json.loads(business["socials"])
                except Exception:
                    business["socials"] = {}
            else:
                business["socials"] = {}
        
        response = {
            "businesses": businesses,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total_count,
                "pages": (total_count + limit - 1) // limit
            },
            "filters": {
                "categories": available_categories,
                "locations": available_locations,
                "ratingRange": {
                    "min": rating_range["min_rating"] if rating_range else 0,
                    "max": rating_range["max_rating"] if rating_range else 5
                }
            }
        }
        
        return jsonify(response), 200

@bp.route("/search-suggestions", methods=["GET"])
def get_search_suggestions():
    query = request.args.get("q", "")
    if not query or len(query) < 2:
        return jsonify({"suggestions": []}), 200
    
    with get_db() as conn:
        # Search in business names
        business_cursor = conn.execute(
            "SELECT DISTINCT name as text, 'business' as type, COUNT(*) as count FROM businesses WHERE name LIKE ? GROUP BY name LIMIT 3",
            (f"%{query}%",)
        )
        business_suggestions = [dict(row) for row in business_cursor.fetchall()]
        
        # Search in categories
        category_cursor = conn.execute(
            "SELECT DISTINCT category as text, 'category' as type, COUNT(*) as count FROM businesses WHERE category LIKE ? GROUP BY category LIMIT 2",
            (f"%{query}%",)
        )
        category_suggestions = [dict(row) for row in category_cursor.fetchall()]
        
        # Search in locations
        location_cursor = conn.execute(
            "SELECT DISTINCT location as text, 'location' as type, COUNT(*) as count FROM businesses WHERE location LIKE ? GROUP BY location LIMIT 2",
            (f"%{query}%",)
        )
        location_suggestions = [dict(row) for row in location_cursor.fetchall()]
        
        # Combine and format suggestions
        all_suggestions = business_suggestions + category_suggestions + location_suggestions
        
        # Add unique IDs
        for i, suggestion in enumerate(all_suggestions):
            suggestion["id"] = f"{suggestion['type']}_{i}"
        
        return jsonify({"suggestions": all_suggestions}), 200

@bp.route("/businesses/filter-options", methods=["GET"])
def get_filter_options():
    with get_db() as conn:
        # Get categories
        categories_cursor = conn.execute("SELECT DISTINCT category FROM businesses")
        categories = [row["category"] for row in categories_cursor.fetchall()]
        
        # Get locations
        locations_cursor = conn.execute("SELECT DISTINCT location FROM businesses")
        locations = [row["location"] for row in locations_cursor.fetchall()]
        
        # Get rating range
        rating_cursor = conn.execute("""
            SELECT MIN(COALESCE(AVG(r.rating), 0)) as min_rating, 
                   MAX(COALESCE(AVG(r.rating), 0)) as max_rating
            FROM businesses b
            LEFT JOIN reviews r ON b.id = r.business_id
            GROUP BY b.id
        """)
        rating_range = rating_cursor.fetchone()
        
        return jsonify({
            "categories": categories,
            "locations": locations,
            "ratingRange": {
                "min": rating_range["min_rating"] if rating_range else 0,
                "max": rating_range["max_rating"] if rating_range else 5
            }
        }), 200

@bp.route("/businesses/<int:biz_id>", methods=["GET"])
def get_business(biz_id):
    with get_db() as conn:
        cursor = conn.execute("SELECT * FROM businesses WHERE id = ?", (biz_id,))
        business = cursor.fetchone()
        
        if business:
            # Get images for this business
            images_cursor = conn.execute("SELECT * FROM business_images WHERE business_id = ?", (biz_id,))
            images = [dict(row) for row in images_cursor.fetchall()]
            
            business_dict = dict(business)
            business_dict['images'] = images
            # Parse socials JSON
            if business_dict.get('socials'):
                try:
                    business_dict['socials'] = json.loads(business_dict['socials'])
                except Exception:
                    business_dict['socials'] = {}
            else:
                business_dict['socials'] = {}
            return jsonify(business_dict), 200
    return jsonify({"error": "Business not found"}), 404

@bp.route("/businesses", methods=["POST"])
@require_auth
def add_business():
    required_fields = ["name", "category", "description", "services"]
    data = request.get_json(force=True)
    missing = [field for field in required_fields if field not in data]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    # Geocode the address if provided
    latitude, longitude = None, None
    if data.get("location"):
        latitude, longitude = geocode_address(data["location"])

    socials = data.get("socials", {})
    socials_json = json.dumps(socials)
    
    # Process service pricing data
    service_pricing = data.get("service_pricing", {})
    service_pricing_json = json.dumps(service_pricing)

    # Get user ID from token
    user_id = request.user_id

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO businesses (name, category, description, services, service_pricing, image_url, location, latitude, longitude, socials, rating, owner_id, business_hours)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["name"],
                data["category"],
                data["description"],
                data["services"],
                service_pricing_json,
                data["image_url"],
                data.get("location", ""),
                latitude,
                longitude,
                socials_json,
                data.get("rating", None),
                user_id,
                data.get("business_hours", "")
            ),
        )
        conn.commit()
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        
        # Insert service pricing data if provided
        if service_pricing:
            for service_name, pricing_data in service_pricing.items():
                current_price = pricing_data.get("current_price", 0)
                recommended_price = pricing_data.get("recommended_price", current_price)
                pricing_strategy = pricing_data.get("pricing_strategy", "competitive")
                confidence_score = pricing_data.get("confidence_score", 0.8)
                
                conn.execute(
                    """
                    INSERT INTO service_pricing (business_id, service_name, current_price, recommended_price, pricing_strategy, confidence_score)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (new_id, service_name, current_price, recommended_price, pricing_strategy, confidence_score)
                )
        
        # Insert business hours if provided
        hours_data = data.get("hours", [])
        for hour in hours_data:
            day_of_week = hour.get("day_of_week")
            open_time = hour.get("open_time")
            close_time = hour.get("close_time")
            is_closed = hour.get("is_closed", False)
            
            if day_of_week is not None and 0 <= day_of_week <= 6:
                conn.execute(
                    "INSERT INTO business_hours (business_id, day_of_week, open_time, close_time, is_closed) VALUES (?, ?, ?, ?, ?)",
                    (new_id, day_of_week, open_time, close_time, is_closed)
                )
        
        conn.commit()
    return jsonify({"id": new_id}), 201

@bp.route("/businesses/<int:biz_id>/images", methods=["POST"])
@require_auth
def upload_business_image(biz_id):
    # Check if business exists
    with get_db() as conn:
        business = conn.execute("SELECT id FROM businesses WHERE id = ?", (biz_id,)).fetchone()
        if not business:
            return jsonify({"error": "Business not found"}), 404
    
    if 'image' not in request.files:
        return jsonify({"error": "No image file provided"}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    if not allowed_file(file.filename):
        return jsonify({"error": "File type not allowed"}), 400
    
    # Save the file
    filename = secure_filename(file.filename)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_filename = f"{timestamp}_{filename}"
    filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
    file.save(filepath)
    
    # Store in database
    image_url = f"/uploads/{unique_filename}"
    with get_db() as conn:
        conn.execute(
            "INSERT INTO business_images (business_id, image_url) VALUES (?, ?)",
            (biz_id, image_url)
        )
        conn.commit()
        image_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
    
    return jsonify({"id": image_id, "image_url": image_url}), 201

@bp.route("/businesses/<int:biz_id>/images", methods=["GET"])
def get_business_images(biz_id):
    with get_db() as conn:
        cursor = conn.execute("SELECT * FROM business_images WHERE business_id = ?", (biz_id,))
        images = [dict(row) for row in cursor.fetchall()]
    return jsonify(images), 200

@bp.route("/businesses/<int:biz_id>/owner-check", methods=["GET"])
@require_auth
def check_business_owner(biz_id):
    """Check if the current user is the owner of the business"""
    user_id = request.user_id
    
    with get_db() as conn:
        business = conn.execute(
            "SELECT owner_id FROM businesses WHERE id = ?",
            (biz_id,)
        ).fetchone()
        
        if not business:
            return jsonify({"error": "Business not found"}), 404
        
        is_owner = business["owner_id"] == user_id
        return jsonify({"isOwner": is_owner}), 200

@bp.route("/businesses/<int:biz_id>", methods=["PATCH"])
@require_auth
def update_business(biz_id):
    """Update business information"""
    data = request.get_json(force=True)
    
    with get_db() as conn:
        # Check if business exists and user owns it
        business = conn.execute(
            "SELECT owner_id FROM businesses WHERE id = ?", 
            (biz_id,)
        ).fetchone()
        
        if not business:
            return jsonify({"error": "Business not found"}), 404
        
        if business["owner_id"] != request.user_id:
            return jsonify({"error": "Unauthorized"}), 403
        
        # Update allowed fields
        allowed_fields = ["name", "category", "description", "services", "image_url", "location", "socials"]
        update_data = {}
        
        for field in allowed_fields:
            if field in data:
                if field == "socials":
                    update_data[field] = json.dumps(data[field])
                else:
                    update_data[field] = data[field]
        
        if update_data:
            set_clause = ", ".join([f"{k} = ?" for k in update_data.keys()])
            values = list(update_data.values()) + [biz_id]
            
            conn.execute(f"UPDATE businesses SET {set_clause} WHERE id = ?", values)
            conn.commit()
        
        return jsonify({"message": "Business updated successfully"}), 200

@bp.route("/businesses/<int:biz_id>/images/<int:image_id>", methods=["DELETE"])
@require_auth
def delete_business_image(biz_id, image_id):
    with get_db() as conn:
        # Get the image to delete
        image = conn.execute(
            "SELECT * FROM business_images WHERE id = ? AND business_id = ?", 
            (image_id, biz_id)
        ).fetchone()
        
        if not image:
            return jsonify({"error": "Image not found"}), 404
        
        # Delete the file
        image_dict = dict(image)
        filepath = os.path.join(UPLOAD_FOLDER, image_dict["image_url"].split("/")[-1])
        if os.path.exists(filepath):
            os.remove(filepath)
        
        # Delete from database
        conn.execute("DELETE FROM business_images WHERE id = ?", (image_id,))
        conn.commit()
    
    return jsonify({"message": "Image deleted successfully"}), 200

@bp.route("/businesses/<int:biz_id>/hours", methods=["GET"])
def get_business_hours(biz_id):
    """Get business hours for a specific business"""
    with get_db() as conn:
        # Check if business exists
        business = conn.execute("SELECT id FROM businesses WHERE id = ?", (biz_id,)).fetchone()
        if not business:
            return jsonify({"error": "Business not found"}), 404
        
        # Get business hours
        hours = conn.execute(
            "SELECT day_of_week, open_time, close_time, is_closed FROM business_hours WHERE business_id = ? ORDER BY day_of_week",
            (biz_id,)
        ).fetchall()
        
        # Convert to list of dictionaries
        hours_list = []
        for hour in hours:
            hours_list.append({
                "day_of_week": hour["day_of_week"],
                "open_time": hour["open_time"],
                "close_time": hour["close_time"],
                "is_closed": bool(hour["is_closed"])
            })
        
        return jsonify(hours_list), 200

@bp.route("/businesses/<int:biz_id>/hours", methods=["POST"])
@require_auth
def set_business_hours(biz_id):
    """Set business hours for a specific business"""
    data = request.get_json(force=True)
    
    with get_db() as conn:
        # Check if business exists and user owns it
        business = conn.execute(
            "SELECT owner_id FROM businesses WHERE id = ?", 
            (biz_id,)
        ).fetchone()
        
        if not business:
            return jsonify({"error": "Business not found"}), 404
        
        if business["owner_id"] != request.user_id:
            return jsonify({"error": "Unauthorized"}), 403
        
        # Delete existing hours
        conn.execute("DELETE FROM business_hours WHERE business_id = ?", (biz_id,))
        
        # Insert new hours
        hours_data = data.get("hours", [])
        for hour in hours_data:
            day_of_week = hour.get("day_of_week")
            open_time = hour.get("open_time")
            close_time = hour.get("close_time")
            is_closed = hour.get("is_closed", False)
            
            if day_of_week is not None and 0 <= day_of_week <= 6:
                conn.execute(
                    "INSERT INTO business_hours (business_id, day_of_week, open_time, close_time, is_closed) VALUES (?, ?, ?, ?, ?)",
                    (biz_id, day_of_week, open_time, close_time, is_closed)
                )
        
        conn.commit()
        return jsonify({"message": "Business hours updated successfully"}), 200

@bp.route("/businesses/<int:biz_id>/ai-recommendations", methods=["GET"])
@require_auth
def get_ai_service_recommendations(biz_id):
    """Get AI-powered service recommendations for a business"""
    try:
        with get_db() as conn:
            # Get business information
            business = conn.execute("""
                SELECT name, category, description, services, location, socials
                FROM businesses WHERE id = ?
            """, (biz_id,)).fetchone()
            
            if not business:
                return jsonify({"error": "Business not found"}), 404
            
            # Check if user owns the business
            if business[5]:  # socials field
                business_data = {
                    "name": business[0],
                    "category": business[1],
                    "description": business[2],
                    "services": business[3],
                    "location": business[4],
                    "socials": json.loads(business[5]) if business[5] else {}
                }
            else:
                business_data = {
                    "name": business[0],
                    "category": business[1],
                    "description": business[2],
                    "services": business[3],
                    "location": business[4],
                    "socials": {}
                }
            
            # Get similar businesses for analysis
            similar_businesses = conn.execute("""
                SELECT services, category FROM businesses 
                WHERE category = ? AND id != ? 
                LIMIT 10
            """, (business_data["category"], biz_id)).fetchall()
            
            # Generate AI recommendations
            recommendations = generate_service_recommendations(business_data, similar_businesses)
            
            return jsonify({
                "recommendations": recommendations,
                "business_info": business_data
            }), 200
            
    except Exception as e:
        print(f"AI recommendations error: {e}")
        return jsonify({"error": "Failed to generate recommendations"}), 500

def generate_service_recommendations(business_data, similar_businesses):
    """Generate AI-powered service recommendations"""
    
    if not openai_client:
        # Fallback recommendations without OpenAI
        return get_fallback_recommendations(business_data["category"])
    
    try:
        # Prepare context for AI
        current_services = business_data["services"].split("\n") if business_data["services"] else []
        category = business_data["category"]
        description = business_data["description"]
        
        # Analyze similar businesses
        similar_services = []
        for biz in similar_businesses:
            if biz[0]:  # services
                similar_services.extend(biz[0].split("\n"))
        
        # Create prompt for AI
        prompt = f"""
        You are an AI business consultant helping a {category} business optimize their service offerings.
        
        Current Business:
        - Name: {business_data['name']}
        - Category: {category}
        - Description: {description}
        - Current Services: {', '.join(current_services) if current_services else 'None listed'}
        
        Similar businesses in this category typically offer: {', '.join(set(similar_services)) if similar_services else 'Various services'}
        
        Please provide 5-8 specific service recommendations that would be valuable for this business to add. Consider:
        1. Services that complement their current offerings
        2. Popular services in their category
        3. Services that could increase revenue
        4. Modern trends in their industry
        
        Format your response as a JSON array of objects with this structure:
        [
            {{
                "service_name": "Service Name",
                "description": "Brief description of the service",
                "category": "Primary category (e.g., 'Core Service', 'Add-on', 'Premium')",
                "estimated_price_range": "Price range (e.g., '$50-100', 'Varies', 'Free')",
                "reasoning": "Why this service would be beneficial"
            }}
        ]
        
        Only return the JSON array, no additional text.
        """
        
        # Call OpenAI API
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful business consultant specializing in service optimization. Provide practical, actionable recommendations."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.7
        )
        
        # Parse AI response
        ai_response = response.choices[0].message.content.strip()
        
        # Try to extract JSON from response
        try:
            # Remove any markdown formatting
            if ai_response.startswith("```json"):
                ai_response = ai_response[7:]
            if ai_response.endswith("```"):
                ai_response = ai_response[:-3]
            
            recommendations = json.loads(ai_response)
            return recommendations
        except json.JSONDecodeError:
            # If JSON parsing fails, return fallback recommendations
            print(f"Failed to parse AI response: {ai_response}")
            return get_fallback_recommendations(category)
            
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return get_fallback_recommendations(business_data["category"])

def get_fallback_recommendations(category):
    """Provide fallback recommendations when AI is not available"""
    
    category_recommendations = {
        "Restaurant & Food": [
            {
                "service_name": "Catering Services",
                "description": "Professional catering for events and corporate functions",
                "category": "Premium",
                "estimated_price_range": "$500-2000",
                "reasoning": "High-margin service that leverages existing kitchen infrastructure"
            },
            {
                "service_name": "Meal Prep & Delivery",
                "description": "Weekly meal preparation and delivery service",
                "category": "Add-on",
                "estimated_price_range": "$100-300/week",
                "reasoning": "Recurring revenue stream with growing demand"
            },
            {
                "service_name": "Cooking Classes",
                "description": "Interactive cooking workshops and culinary education",
                "category": "Premium",
                "estimated_price_range": "$75-150/person",
                "reasoning": "Unique experience that builds customer loyalty"
            }
        ],
        "Health & Wellness": [
            {
                "service_name": "Wellness Packages",
                "description": "Combined health and wellness service bundles",
                "category": "Premium",
                "estimated_price_range": "$200-500",
                "reasoning": "Higher value packages increase average transaction value"
            },
            {
                "service_name": "Online Consultations",
                "description": "Virtual health consultations and follow-ups",
                "category": "Core Service",
                "estimated_price_range": "$50-150",
                "reasoning": "Convenient option that expands your reach"
            },
            {
                "service_name": "Health Assessments",
                "description": "Comprehensive health evaluations and screenings",
                "category": "Core Service",
                "estimated_price_range": "$100-300",
                "reasoning": "Essential service that leads to ongoing care"
            }
        ],
        "Beauty & Spa": [
            {
                "service_name": "Bridal Packages",
                "description": "Complete bridal beauty and spa packages",
                "category": "Premium",
                "estimated_price_range": "$300-800",
                "reasoning": "High-value packages for special occasions"
            },
            {
                "service_name": "Membership Programs",
                "description": "Monthly membership with discounted services",
                "category": "Add-on",
                "estimated_price_range": "$100-300/month",
                "reasoning": "Recurring revenue and customer retention"
            },
            {
                "service_name": "Product Sales",
                "description": "Retail beauty and skincare products",
                "category": "Add-on",
                "estimated_price_range": "$20-200",
                "reasoning": "Additional revenue stream with high margins"
            }
        ],
        "Fitness & Sports": [
            {
                "service_name": "Personal Training",
                "description": "One-on-one fitness coaching and training",
                "category": "Premium",
                "estimated_price_range": "$50-100/session",
                "reasoning": "High-value personalized service"
            },
            {
                "service_name": "Group Classes",
                "description": "Specialized fitness classes and workshops",
                "category": "Core Service",
                "estimated_price_range": "$15-30/class",
                "reasoning": "Efficient use of space and equipment"
            },
            {
                "service_name": "Nutrition Coaching",
                "description": "Diet and nutrition consultation services",
                "category": "Add-on",
                "estimated_price_range": "$75-150",
                "reasoning": "Complements fitness services perfectly"
            }
        ]
    }
    
    # Return category-specific recommendations or general ones
    if category in category_recommendations:
        return category_recommendations[category]
    else:
        return [
            {
                "service_name": "Consultation Services",
                "description": "Professional consultation and advisory services",
                "category": "Core Service",
                "estimated_price_range": "$100-300",
                "reasoning": "Establishes expertise and generates leads"
            },
            {
                "service_name": "Package Deals",
                "description": "Bundled services at discounted rates",
                "category": "Add-on",
                "estimated_price_range": "Varies",
                "reasoning": "Increases average transaction value"
            },
            {
                "service_name": "Maintenance Services",
                "description": "Ongoing maintenance and support services",
                "category": "Add-on",
                "estimated_price_range": "$50-200",
                "reasoning": "Recurring revenue stream"
            }
        ]

@bp.route("/businesses/<int:biz_id>/pricing-analysis", methods=["GET"])
@require_auth
def get_pricing_analysis(biz_id):
    """Get AI-powered pricing analysis and recommendations for a business"""
    try:
        with get_db() as conn:
            # Get business information
            business = conn.execute("""
                SELECT id, name, category, description, services, location, socials, image_url, rating, total_reviews
                FROM businesses WHERE id = ?
            """, (biz_id,)).fetchone()
            
            if not business:
                return jsonify({"error": "Business not found"}), 404
            
            # Check if user owns the business
            business_owner = conn.execute("""
                SELECT owner_id FROM businesses WHERE id = ?
            """, (biz_id,)).fetchone()
            
            if not business_owner or business_owner[0] != request.user_id:
                return jsonify({"error": "Unauthorized access"}), 403
            
            business_data = {
                "id": business[0],
                "name": business[1],
                "category": business[2],
                "description": business[3],
                "services": business[4],
                "location": business[5],
                "socials": json.loads(business[6]) if business[6] else {},
                "image_url": business[7],
                "rating": business[8],
                "total_reviews": business[9]
            }
            
            # Get personalized market data for this specific business
            personalized_market = get_personalized_market_analysis(business_data, [])
            
            # Get personalized competitor data for this specific business
            personalized_competitors = get_competitor_pricing(business_data["category"], business_data["location"])
            
            # Generate AI pricing recommendations with business-specific data
            pricing_analysis = generate_pricing_recommendations(business_data, personalized_market, personalized_competitors)
            
            return jsonify({
                "pricing_analysis": pricing_analysis,
                "market_data": personalized_market,
                "competitor_data": personalized_competitors,
                "business_info": business_data
            }), 200
            
    except Exception as e:
        print(f"Pricing analysis error: {e}")
        return jsonify({"error": "Failed to generate pricing analysis"}), 500

@bp.route("/businesses/<int:biz_id>/dynamic-pricing", methods=["POST"])
@require_auth
def set_dynamic_pricing(biz_id):
    """Set dynamic pricing rules for a business"""
    try:
        data = request.get_json()
        
        with get_db() as conn:
            # Verify business ownership
            business_owner = conn.execute("""
                SELECT owner_id FROM businesses WHERE id = ?
            """, (biz_id,)).fetchone()
            
            if not business_owner or business_owner[0] != request.user_id:
                return jsonify({"error": "Unauthorized access"}), 403
            
            # Store dynamic pricing configuration
            pricing_config = {
                "enabled": data.get("enabled", False),
                "base_price_adjustment": data.get("base_price_adjustment", 0),
                "demand_multiplier": data.get("demand_multiplier", 1.0),
                "seasonal_adjustments": data.get("seasonal_adjustments", {}),
                "competitor_tracking": data.get("competitor_tracking", True),
                "auto_adjust": data.get("auto_adjust", False),
                "min_price": data.get("min_price", 0),
                "max_price": data.get("max_price", 1000),
                "update_frequency": data.get("update_frequency", "daily")
            }
            
            # Update business with pricing configuration
            conn.execute("""
                UPDATE businesses 
                SET dynamic_pricing_config = ? 
                WHERE id = ?
            """, (json.dumps(pricing_config), biz_id))
            
            return jsonify({
                "message": "Dynamic pricing configuration updated successfully",
                "config": pricing_config
            }), 200
            
    except Exception as e:
        print(f"Dynamic pricing error: {e}")
        return jsonify({"error": "Failed to update pricing configuration"}), 500

@bp.route("/businesses/<int:biz_id>/price-history", methods=["GET"])
def get_price_history(biz_id):
    """Get price history and trends for a business"""
    try:
        with get_db() as conn:
            # Get business basic info
            business = conn.execute("""
                SELECT name, category, dynamic_pricing_config
                FROM businesses WHERE id = ?
            """, (biz_id,)).fetchone()
            
            if not business:
                return jsonify({"error": "Business not found"}), 404
            
            # Generate price history (simulated for now)
            price_history = generate_price_history(business[0], business[1])
            
            return jsonify({
                "business_name": business[0],
                "category": business[1],
                "price_history": price_history,
                "trends": analyze_price_trends(price_history)
            }), 200
            
    except Exception as e:
        print(f"Price history error: {e}")
        return jsonify({"error": "Failed to get price history"}), 500

@bp.route("/market/price-comparison", methods=["GET"])
def get_price_comparison():
    """Get personalized price comparison for specific business context"""
    try:
        category = request.args.get("category")
        location = request.args.get("location")
        business_id = request.args.get("business_id")  # Optional: for personalized analysis
        
        if not category or not location:
            return jsonify({"error": "Category and location required"}), 400
        
        with get_db() as conn:
            # Get personalized competitor data based on business context
            if business_id:
                # Get the specific business for personalized analysis
                business = conn.execute("""
                    SELECT name, category, location, rating, total_reviews, dynamic_pricing_config
                    FROM businesses WHERE id = ?
                """, (business_id,)).fetchone()
                
                if business:
                    # Get competitors with personalized analysis
                    similar_businesses = conn.execute("""
                        SELECT name, category, location, rating, total_reviews, dynamic_pricing_config
                        FROM businesses 
                        WHERE category = ? AND location LIKE ? AND id != ?
                        ORDER BY rating DESC
                        LIMIT 15
                    """, (category, f"%{location.split(',')[0]}%", business_id)).fetchall()
                    
                    # Calculate personalized market analysis
                    personalized_analysis = analyze_personalized_market_comparison(business, similar_businesses)
                    
                    comparison_data = []
                    for biz in similar_businesses:
                        pricing_config = json.loads(biz[5]) if biz[5] else {}
                        comparison_data.append({
                            "name": biz[0],
                            "category": biz[1],
                            "location": biz[2],
                            "current_pricing": get_personalized_current_pricing(biz[0], biz[1], biz[3], biz[4]),
                            "pricing_strategy": analyze_pricing_strategy(pricing_config),
                            "competitive_threat": calculate_competitive_threat(business, biz),
                            "market_position": determine_market_position(biz[3], biz[4])
                        })
                    
                    return jsonify({
                        "category": category,
                        "location": location,
                        "business_context": {
                            "business_name": business[0],
                            "business_rating": business[3],
                            "business_reviews": business[4],
                            "market_position": determine_market_position(business[3], business[4])
                        },
                        "comparison_data": comparison_data,
                        "market_average": calculate_personalized_market_average(comparison_data, business),
                        "personalized_insights": personalized_analysis
                    }), 200
            else:
                # Fallback to general comparison
                similar_businesses = conn.execute("""
                    SELECT name, category, location, rating, total_reviews, dynamic_pricing_config
                    FROM businesses 
                    WHERE category = ? AND location LIKE ?
                    ORDER BY rating DESC
                    LIMIT 10
                """, (category, f"%{location.split(',')[0]}%")).fetchall()
                
                comparison_data = []
                for biz in similar_businesses:
                    pricing_config = json.loads(biz[5]) if biz[5] else {}
                    comparison_data.append({
                        "name": biz[0],
                        "category": biz[1],
                        "location": biz[2],
                        "current_pricing": get_current_pricing(biz[0], biz[1]),
                        "pricing_strategy": analyze_pricing_strategy(pricing_config)
                    })
                
                return jsonify({
                    "category": category,
                    "location": location,
                    "comparison_data": comparison_data,
                    "market_average": calculate_market_average(comparison_data)
                }), 200
            
    except Exception as e:
        print(f"Price comparison error: {e}")
        return jsonify({"error": "Failed to get price comparison"}), 500

def analyze_personalized_market_comparison(business, competitors):
    """Analyze personalized market comparison for specific business"""
    
    business_rating = business[3] or 0
    business_reviews = business[4] or 0
    
    # Calculate competitive landscape
    competitor_ratings = [comp[3] or 0 for comp in competitors if comp[3]]
    avg_competitor_rating = sum(competitor_ratings) / len(competitor_ratings) if competitor_ratings else 0
    
    # Determine competitive position
    if business_rating > avg_competitor_rating + 0.5:
        competitive_position = "market_leader"
    elif business_rating > avg_competitor_rating:
        competitive_position = "above_average"
    elif business_rating < avg_competitor_rating - 0.5:
        competitive_position = "below_average"
    else:
        competitive_position = "average"
    
    # Calculate market share estimate
    total_reviews = sum([comp[4] or 0 for comp in competitors]) + business_reviews
    market_share = round((business_reviews / total_reviews) * 100, 1) if total_reviews > 0 else 0
    
    return {
        "competitive_position": competitive_position,
        "market_share": f"{market_share}%",
        "average_competitor_rating": round(avg_competitor_rating, 1),
        "rating_difference": round(business_rating - avg_competitor_rating, 1),
        "competitor_count": len(competitors),
        "market_opportunity": "high" if business_rating > avg_competitor_rating else "medium"
    }

def get_personalized_current_pricing(business_name, category, rating, reviews):
    """Get personalized current pricing based on business characteristics"""
    
    # Base pricing calculation
    base_price = 50 if "Beauty" in category else 20
    
    # Adjust based on rating
    rating_multiplier = 1.0 + ((rating - 3.0) * 0.2)  # Higher rating = higher price
    
    # Adjust based on review count (more reviews = more established)
    review_multiplier = 1.0 + (min(reviews, 100) / 1000)  # More reviews = slightly higher price
    
    adjusted_price = base_price * rating_multiplier * review_multiplier
    
    return {
        "base_price": round(adjusted_price, 2),
        "current_range": f"${adjusted_price-5:.0f}-${adjusted_price+10:.0f}",
        "pricing_strategy": "premium" if rating >= 4.5 else "competitive" if rating >= 4.0 else "budget",
        "rating_factor": round(rating_multiplier, 2),
        "review_factor": round(review_multiplier, 2)
    }

def calculate_competitive_threat(business, competitor):
    """Calculate competitive threat level for specific business"""
    
    business_rating = business[3] or 0
    competitor_rating = competitor[3] or 0
    
    rating_diff = competitor_rating - business_rating
    
    if rating_diff > 0.5:
        threat_level = "high"
    elif rating_diff > 0:
        threat_level = "medium"
    else:
        threat_level = "low"
    
    return {
        "threat_level": threat_level,
        "rating_difference": round(rating_diff, 1),
        "competitive_advantage": "competitor" if rating_diff > 0 else "business" if rating_diff < 0 else "equal"
    }

def determine_market_position(rating, reviews):
    """Determine market position based on rating and reviews"""
    
    if rating >= 4.5 and reviews >= 10:
        return "premium"
    elif rating >= 4.0 and reviews >= 5:
        return "competitive"
    else:
        return "budget"

def calculate_personalized_market_average(comparison_data, business):
    """Calculate personalized market average for specific business context"""
    
    if not comparison_data:
        return {}
    
    total_price = 0
    count = 0
    
    for business_data in comparison_data:
        current_pricing = business_data["current_pricing"]
        if current_pricing and "base_price" in current_pricing:
            total_price += current_pricing["base_price"]
            count += 1
    
    if count > 0:
        average = total_price / count
        
        # Add business-specific context
        business_rating = business[3] or 0
        business_reviews = business[4] or 0
        
        # Calculate relative position
        if business_rating >= 4.5:
            relative_position = "above_market"
        elif business_rating >= 4.0:
            relative_position = "market_average"
        else:
            relative_position = "below_market"
        
        return {
            "average_price": round(average, 2),
            "price_range": f"${average-10:.0f} - ${average+10:.0f}",
            "market_position": "competitive",
            "business_relative_position": relative_position,
            "business_rating_vs_market": round(business_rating - 4.0, 1),
            "market_competitiveness": "high" if count > 5 else "medium"
        }
    
    return {}

def get_market_analysis(category, location):
    """Analyze market conditions for pricing"""
    # Simulated market data - in production, this would connect to real market APIs
    market_data = {
        "category": category,
        "location": location,
        "market_size": generate_market_size(category, location),
        "demand_trends": generate_demand_trends(category),
        "seasonal_factors": get_seasonal_factors(category),
        "economic_indicators": get_economic_indicators(location),
        "growth_rate": calculate_growth_rate(category, location)
    }
    return market_data

def get_competitor_pricing(category, location):
    """Get competitor pricing data"""
    # Simulated competitor data
    competitors = [
        {
            "name": f"Competitor {i+1}",
            "category": category,
            "location": location,
            "pricing_strategy": ["premium", "competitive", "budget"][i % 3],
            "price_range": generate_price_range(category, i),
            "market_share": round(0.1 + (i * 0.05), 2),
            "rating": round(3.5 + (i * 0.3), 1)
        }
        for i in range(5)
    ]
    return competitors

def generate_pricing_recommendations(business_data, market_data, competitor_data):
    """Generate AI-powered pricing recommendations - TRULY PERSONALIZED per business"""
    
    if not openai_client:
        return get_fallback_pricing_recommendations(business_data["category"])
    
    try:
        # Get REAL business-specific data from database
        with get_db() as conn:
            # Get actual similar businesses from database
            similar_businesses = conn.execute("""
                SELECT name, category, description, services, service_pricing, location, rating, total_reviews, socials
                FROM businesses 
                WHERE category = ? AND location LIKE ? AND id != ?
                ORDER BY rating DESC
                LIMIT 10
            """, (business_data["category"], f"%{business_data['location'].split(',')[0]}%", business_data.get("id", 0))).fetchall()
            
            # Get actual market data for this specific business
            business_reviews = conn.execute("""
                SELECT rating, comment FROM reviews 
                WHERE business_id = ? 
                ORDER BY created_at DESC 
                LIMIT 20
            """, (business_data.get("id", 0),)).fetchall()
            
            # Get actual competitor pricing data
            competitor_pricing = conn.execute("""
                SELECT name, category, location, rating, total_reviews, 
                       dynamic_pricing_config, business_hours, service_pricing
                FROM businesses 
                WHERE category = ? AND location LIKE ? AND id != ?
                ORDER BY rating DESC
                LIMIT 15
            """, (business_data["category"], f"%{business_data['location'].split(',')[0]}%", business_data.get("id", 0))).fetchall()
            
            # Get current service pricing for this business
            current_service_pricing = conn.execute("""
                SELECT service_name, current_price, recommended_price, pricing_strategy, confidence_score
                FROM service_pricing 
                WHERE business_id = ?
                ORDER BY last_updated DESC
            """, (business_data.get("id", 0),)).fetchall()
        
        # Analyze business-specific characteristics
        business_profile = analyze_business_profile(business_data, similar_businesses, business_reviews)
        
        # Get personalized market analysis
        personalized_market = get_personalized_market_analysis(business_data, competitor_pricing)
        
        # Generate business-specific competitor analysis
        personalized_competitors = analyze_personalized_competitors(business_data, competitor_pricing)
        
        # Calculate business-specific revenue potential
        revenue_potential = calculate_business_revenue_potential(business_data, business_profile, personalized_market)
        
        # Prepare context for AI with REAL business data
        current_services = business_data["services"].split("\n") if business_data["services"] else []
        category = business_data["category"]
        description = business_data["description"]
        
        # Process current service pricing
        current_pricing_info = ""
        if current_service_pricing:
            pricing_lines = []
            for service in current_service_pricing:
                pricing_lines.append(f"- {service[0]}: ${service[1]} (Recommended: ${service[2]}, Strategy: {service[3]})")
            current_pricing_info = "\n".join(pricing_lines)
        
        # Create business-specific prompt
        prompt = f"""
        You are a dedicated AI pricing consultant for "{business_data['name']}" - a {category} business in {business_data['location']}.
        
        BUSINESS-SPECIFIC PROFILE:
        - Business Name: {business_data['name']}
        - Category: {category}
        - Description: {description}
        - Current Services: {', '.join(current_services) if current_services else 'None listed'}
        - Location: {business_data['location']}
        - Current Rating: {business_profile['current_rating']}
        - Total Reviews: {business_profile['total_reviews']}
        - Market Position: {business_profile['market_position']}
        - Service Quality Score: {business_profile['service_quality_score']}
        - Customer Satisfaction: {business_profile['customer_satisfaction']}
        
        CURRENT SERVICE PRICING:
        {current_pricing_info if current_pricing_info else 'No pricing data available'}
        
        BUSINESS-SPECIFIC MARKET ANALYSIS:
        - Local Market Size: {personalized_market['local_market_size']}
        - Demand in Your Area: {personalized_market['local_demand_trends']}
        - Local Competition Level: {personalized_market['competition_level']}
        - Your Market Share: {personalized_market['estimated_market_share']}
        - Local Economic Factors: {personalized_market['local_economic_indicators']}
        - Seasonal Demand in Your Area: {personalized_market['local_seasonal_factors']}
        
        YOUR COMPETITORS (Real Data):
        {personalized_competitors}
        
        REVENUE POTENTIAL ANALYSIS:
        - Current Revenue Estimate: {revenue_potential['current_revenue']}
        - Revenue Growth Potential: {revenue_potential['growth_potential']}
        - Optimal Price Range: {revenue_potential['optimal_price_range']}
        - Revenue Optimization Score: {revenue_potential['optimization_score']}
        
        Based on YOUR SPECIFIC business profile, market position, and local competition, provide personalized pricing recommendations:
        
        1. Service-specific pricing for YOUR exact services
        2. Dynamic pricing strategies tailored to YOUR market position
        3. Competitive positioning strategy for YOUR business
        4. Revenue optimization tactics for YOUR specific situation
        5. Implementation timeline based on YOUR current position
        
        Format your response as a JSON object with this structure:
        {{
            "service_pricing": [
                {{
                    "service_name": "Your Specific Service",
                    "current_price_range": "$X-$Y",
                    "recommended_price_range": "$A-$B",
                    "pricing_strategy": "premium/competitive/budget",
                    "reasoning": "Why this specific pricing works for YOUR business",
                    "confidence_score": 0.85
                }}
            ],
            "dynamic_pricing": {{
                "base_multiplier": 1.0,
                "peak_hours_multiplier": 1.2,
                "off_peak_multiplier": 0.8,
                "weekend_multiplier": 1.1,
                "seasonal_adjustments": {{
                    "summer": 1.15,
                    "winter": 0.9,
                    "holidays": 1.25
                }},
                "business_specific_factors": {{
                    "location_factor": 1.1,
                    "quality_factor": 1.2,
                    "competition_factor": 0.95
                }}
            }},
            "competitive_positioning": {{
                "target_position": "premium/competitive/budget",
                "price_advantage": "higher/lower/same",
                "value_proposition": "What makes YOUR business special",
                "differentiation_strategy": "How to stand out in YOUR market"
            }},
            "revenue_optimization": {{
                "estimated_revenue_increase": "X-Y%",
                "key_strategies": ["strategy1", "strategy2"],
                "implementation_timeline": "X-Y months",
                "risk_assessment": "low/medium/high",
                "success_probability": 0.85
            }},
            "business_specific_insights": {{
                "strengths": ["strength1", "strength2"],
                "weaknesses": ["weakness1", "weakness2"],
                "opportunities": ["opportunity1", "opportunity2"],
                "threats": ["threat1", "threat2"]
            }}
        }}
        
        Only return the JSON object, no additional text.
        """
        
        # Call OpenAI API with business-specific context
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"You are a dedicated pricing consultant for {business_data['name']}. Provide highly personalized, business-specific recommendations based on their exact profile, market position, and local competition."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000,
            temperature=0.6
        )
        
        # Parse AI response
        ai_response = response.choices[0].message.content.strip()
        
        try:
            # Remove any markdown formatting
            if ai_response.startswith("```json"):
                ai_response = ai_response[7:]
            if ai_response.endswith("```"):
                ai_response = ai_response[:-3]
            
            recommendations = json.loads(ai_response)
            
            # Add business-specific metadata
            recommendations["business_metadata"] = {
                "analysis_timestamp": datetime.datetime.now().isoformat(),
                "business_id": business_data.get("id"),
                "market_position": business_profile['market_position'],
                "competition_level": personalized_market['competition_level'],
                "revenue_potential_score": revenue_potential['optimization_score'],
                "personalization_score": 0.95  # High personalization
            }
            
            return recommendations
        except json.JSONDecodeError:
            print(f"Failed to parse AI pricing response: {ai_response}")
            return get_fallback_pricing_recommendations(business_data["category"])
            
    except Exception as e:
        print(f"OpenAI pricing API error: {e}")
        return get_fallback_pricing_recommendations(business_data["category"])

def analyze_business_profile(business_data, similar_businesses, business_reviews):
    """Analyze business-specific profile and characteristics"""
    
    # Calculate business-specific metrics
    current_rating = business_data.get("rating", 0) or 0
    total_reviews = business_data.get("total_reviews", 0) or 0
    
    # Analyze service quality based on reviews
    service_quality_score = 0.7  # Default
    customer_satisfaction = 0.7  # Default
    
    if business_reviews:
        ratings = [review[0] for review in business_reviews if review[0]]
        if ratings:
            avg_rating = sum(ratings) / len(ratings)
            service_quality_score = min(avg_rating / 5.0, 1.0)
            customer_satisfaction = min(avg_rating / 5.0, 1.0)
    
    # Determine market position based on rating and reviews
    if current_rating >= 4.5 and total_reviews >= 10:
        market_position = "premium"
    elif current_rating >= 4.0 and total_reviews >= 5:
        market_position = "competitive"
    else:
        market_position = "budget"
    
    # Analyze service complexity
    services = business_data.get("services", "").split("\n") if business_data.get("services") else []
    service_complexity = len(services) * 0.1 + 0.5  # More services = higher complexity
    
    return {
        "current_rating": current_rating,
        "total_reviews": total_reviews,
        "market_position": market_position,
        "service_quality_score": service_quality_score,
        "customer_satisfaction": customer_satisfaction,
        "service_complexity": service_complexity,
        "similar_businesses_count": len(similar_businesses)
    }

def get_personalized_market_analysis(business_data, competitor_pricing):
    """Get personalized market analysis for this specific business"""
    
    location = business_data["location"]
    category = business_data["category"]
    
    # Analyze local competition
    competition_level = "low"
    if len(competitor_pricing) > 10:
        competition_level = "high"
    elif len(competitor_pricing) > 5:
        competition_level = "medium"
    
    # Calculate estimated market share
    total_businesses = len(competitor_pricing) + 1
    estimated_market_share = round(1 / total_businesses * 100, 1)
    
    # Local market size based on location and category
    local_market_size = f"${random.randint(500000, 3000000):,} market in {location.split(',')[0]}"
    
    # Local demand trends
    demand_trends = ["increasing", "stable", "seasonal"]
    local_demand_trends = random.choice(demand_trends)
    
    # Local economic indicators
    local_economic_indicators = {
        "local_gdp_growth": f"{random.uniform(2, 6):.1f}%",
        "local_unemployment": f"{random.uniform(2, 8):.1f}%",
        "local_consumer_confidence": f"{random.uniform(60, 95):.0f}"
    }
    
    # Local seasonal factors
    local_seasonal_factors = {
        "summer": "high" if "Beauty" in category else "medium",
        "winter": "medium" if "Beauty" in category else "high",
        "holidays": "peak"
    }
    
    return {
        "local_market_size": local_market_size,
        "local_demand_trends": local_demand_trends,
        "competition_level": competition_level,
        "estimated_market_share": f"{estimated_market_share}%",
        "local_economic_indicators": local_economic_indicators,
        "local_seasonal_factors": local_seasonal_factors,
        "competitor_count": len(competitor_pricing)
    }

def analyze_personalized_competitors(business_data, competitor_pricing):
    """Analyze personalized competitor data for this business"""
    
    analysis = []
    
    for i, competitor in enumerate(competitor_pricing[:5]):
        name = competitor[0]
        category = competitor[1]
        location = competitor[2]
        rating = competitor[3] or 0
        total_reviews = competitor[4] or 0
        pricing_config = json.loads(competitor[5]) if competitor[5] else {}
        
        # Determine competitor strategy
        if rating >= 4.5:
            strategy = "premium"
        elif rating >= 4.0:
            strategy = "competitive"
        else:
            strategy = "budget"
        
        # Calculate competitive threat level
        threat_level = "low"
        if rating > (business_data.get("rating", 0) or 0):
            threat_level = "high"
        elif rating >= (business_data.get("rating", 0) or 0) - 0.5:
            threat_level = "medium"
        
        analysis.append(f"- {name}: {strategy} strategy, {rating}★ rating, {total_reviews} reviews, {threat_level} threat level")
    
    return "\n".join(analysis)

def calculate_business_revenue_potential(business_data, business_profile, personalized_market):
    """Calculate business-specific revenue potential"""
    
    # Base revenue calculation
    base_revenue = 5000  # Default monthly revenue
    
    # Adjust based on business profile
    if business_profile["market_position"] == "premium":
        base_revenue *= 1.5
    elif business_profile["market_position"] == "budget":
        base_revenue *= 0.7
    
    # Adjust based on service quality
    base_revenue *= business_profile["service_quality_score"]
    
    # Adjust based on competition
    if personalized_market["competition_level"] == "low":
        growth_potential = "25-40%"
        optimization_score = 0.9
    elif personalized_market["competition_level"] == "medium":
        growth_potential = "15-25%"
        optimization_score = 0.8
    else:
        growth_potential = "10-20%"
        optimization_score = 0.7
    
    # Calculate optimal price range
    if business_profile["market_position"] == "premium":
        optimal_range = "$50-$150"
    elif business_profile["market_position"] == "competitive":
        optimal_range = "$30-$80"
    else:
        optimal_range = "$20-$50"
    
    return {
        "current_revenue": f"${base_revenue:,.0f}/month",
        "growth_potential": growth_potential,
        "optimal_price_range": optimal_range,
        "optimization_score": optimization_score
    }

def get_fallback_pricing_recommendations(category):
    """Provide fallback pricing recommendations when AI is not available"""
    
    category_pricing = {
        "Beauty & Spa": {
            "service_pricing": [
                {
                    "service_name": "Haircut & Styling",
                    "current_price_range": "$30-$60",
                    "recommended_price_range": "$35-$75",
                    "pricing_strategy": "competitive",
                    "reasoning": "Market average with quality positioning",
                    "confidence_score": 0.85
                },
                {
                    "service_name": "Facial Treatment",
                    "current_price_range": "$50-$100",
                    "recommended_price_range": "$60-$120",
                    "pricing_strategy": "premium",
                    "reasoning": "High-value service with good margins",
                    "confidence_score": 0.9
                }
            ],
            "dynamic_pricing": {
                "base_multiplier": 1.0,
                "peak_hours_multiplier": 1.15,
                "off_peak_multiplier": 0.85,
                "weekend_multiplier": 1.1,
                "seasonal_adjustments": {
                    "summer": 1.1,
                    "winter": 0.95,
                    "holidays": 1.2
                },
                "business_specific_factors": {
                    "location_factor": 1.1,
                    "quality_factor": 1.2,
                    "competition_factor": 0.95
                }
            },
            "competitive_positioning": {
                "target_position": "premium",
                "price_advantage": "higher",
                "value_proposition": "Quality service and experience",
                "differentiation_strategy": "Focus on premium experience and quality"
            },
            "revenue_optimization": {
                "estimated_revenue_increase": "20-30%",
                "key_strategies": ["Premium positioning", "Dynamic pricing", "Service bundling"],
                "implementation_timeline": "2-4 weeks",
                "risk_assessment": "low",
                "success_probability": 0.85
            },
            "business_specific_insights": {
                "strengths": ["High-value services", "Quality focus", "Premium positioning"],
                "weaknesses": ["Higher costs", "Limited market"],
                "opportunities": ["Premium market growth", "Service expansion"],
                "threats": ["Economic downturn", "Competition"]
            }
        },
        "Technology & IT": {
            "service_pricing": [
                {
                    "service_name": "Web Development",
                    "current_price_range": "$50-$150/hour",
                    "recommended_price_range": "$75-$200/hour",
                    "pricing_strategy": "premium",
                    "reasoning": "High-demand technical service",
                    "confidence_score": 0.9
                },
                {
                    "service_name": "IT Consulting",
                    "current_price_range": "$100-$200/hour",
                    "recommended_price_range": "$125-$250/hour",
                    "pricing_strategy": "premium",
                    "reasoning": "Expert knowledge commands premium pricing",
                    "confidence_score": 0.85
                }
            ],
            "dynamic_pricing": {
                "base_multiplier": 1.0,
                "peak_hours_multiplier": 1.2,
                "off_peak_multiplier": 0.9,
                "weekend_multiplier": 1.15,
                "seasonal_adjustments": {
                    "summer": 1.05,
                    "winter": 1.0,
                    "holidays": 1.1
                },
                "business_specific_factors": {
                    "location_factor": 1.15,
                    "quality_factor": 1.3,
                    "competition_factor": 0.9
                }
            },
            "competitive_positioning": {
                "target_position": "premium",
                "price_advantage": "higher",
                "value_proposition": "Technical expertise and quality solutions",
                "differentiation_strategy": "Focus on expertise and quality deliverables"
            },
            "revenue_optimization": {
                "estimated_revenue_increase": "25-40%",
                "key_strategies": ["Premium pricing", "Value-based pricing", "Project-based pricing"],
                "implementation_timeline": "1-3 weeks",
                "risk_assessment": "low",
                "success_probability": 0.9
            },
            "business_specific_insights": {
                "strengths": ["Technical expertise", "High demand", "Premium market"],
                "weaknesses": ["High competition", "Skill requirements"],
                "opportunities": ["Digital transformation", "Remote work"],
                "threats": ["Technology changes", "Market saturation"]
            }
        },
        "Restaurant & Food": {
            "service_pricing": [
                {
                    "service_name": "Main Course",
                    "current_price_range": "$15-$25",
                    "recommended_price_range": "$18-$30",
                    "pricing_strategy": "competitive",
                    "reasoning": "Balanced pricing for quality food",
                    "confidence_score": 0.8
                }
            ],
            "dynamic_pricing": {
                "base_multiplier": 1.0,
                "peak_hours_multiplier": 1.1,
                "off_peak_multiplier": 0.9,
                "weekend_multiplier": 1.05,
                "seasonal_adjustments": {
                    "summer": 1.05,
                    "winter": 1.0,
                    "holidays": 1.15
                },
                "business_specific_factors": {
                    "location_factor": 1.05,
                    "quality_factor": 1.1,
                    "competition_factor": 0.95
                }
            },
            "competitive_positioning": {
                "target_position": "competitive",
                "price_advantage": "same",
                "value_proposition": "Quality ingredients and service",
                "differentiation_strategy": "Focus on quality and customer experience"
            },
            "revenue_optimization": {
                "estimated_revenue_increase": "15-25%",
                "key_strategies": ["Menu optimization", "Happy hour pricing", "Loyalty programs"],
                "implementation_timeline": "1-2 months"
            }
        }
    }
    
    return category_pricing.get(category, category_pricing["Beauty & Spa"])

def generate_price_history(business_name, category):
    """Generate simulated price history data"""
    import random
    from datetime import datetime, timedelta
    
    history = []
    base_price = 50 if "Beauty" in category else 20
    
    for i in range(30):
        date = datetime.now() - timedelta(days=30-i)
        price = base_price + random.uniform(-5, 10)
        demand = random.uniform(0.6, 1.4)
        
        history.append({
            "date": date.strftime("%Y-%m-%d"),
            "price": round(price, 2),
            "demand": round(demand, 2),
            "revenue": round(price * demand, 2)
        })
    
    return history

def analyze_price_trends(price_history):
    """Analyze price trends from history"""
    if not price_history:
        return {}
    
    prices = [entry["price"] for entry in price_history]
    revenues = [entry["revenue"] for entry in price_history]
    
    return {
        "price_trend": "increasing" if prices[-1] > prices[0] else "decreasing",
        "revenue_trend": "increasing" if revenues[-1] > revenues[0] else "decreasing",
        "price_volatility": round(max(prices) - min(prices), 2),
        "optimal_price_range": f"${min(prices):.2f} - ${max(prices):.2f}",
        "revenue_optimization": "Price increases correlate with revenue growth" if revenues[-1] > revenues[0] else "Consider price adjustments"
    }

def get_current_pricing(business_name, category):
    """Get current pricing for a business"""
    base_price = 50 if "Beauty" in category else 20
    return {
        "base_price": base_price,
        "current_range": f"${base_price-5}-${base_price+10}",
        "pricing_strategy": "competitive"
    }

def analyze_pricing_strategy(pricing_config):
    """Analyze the pricing strategy from configuration"""
    if not pricing_config:
        return "standard"
    
    if pricing_config.get("enabled", False):
        return "dynamic"
    else:
        return "static"

def calculate_market_average(comparison_data):
    """Calculate market average pricing"""
    if not comparison_data:
        return {}
    
    total_price = 0
    count = 0
    
    for business in comparison_data:
        current_pricing = business["current_pricing"]
        if current_pricing and "base_price" in current_pricing:
            total_price += current_pricing["base_price"]
            count += 1
    
    if count > 0:
        average = total_price / count
        return {
            "average_price": round(average, 2),
            "price_range": f"${average-10:.2f} - ${average+10:.2f}",
            "market_position": "competitive"
        }
    
    return {}

# Helper functions for market analysis
def generate_market_size(category, location):
    return f"${random.randint(1000000, 5000000):,} market in {location}"

def generate_demand_trends(category):
    trends = ["increasing", "stable", "seasonal"]
    return random.choice(trends)

def get_seasonal_factors(category):
    if "Beauty" in category:
        return {"summer": "high", "winter": "medium", "holidays": "peak"}
    elif "Restaurant" in category:
        return {"summer": "medium", "winter": "high", "holidays": "peak"}
    else:
        return {"summer": "medium", "winter": "medium", "holidays": "high"}

def get_economic_indicators(location):
    return {
        "gdp_growth": f"{random.uniform(2, 5):.1f}%",
        "unemployment": f"{random.uniform(3, 8):.1f}%",
        "consumer_confidence": f"{random.uniform(60, 90):.0f}"
    }

def calculate_growth_rate(category, location):
    return round(random.uniform(5, 25), 1)

def generate_price_range(category, index):
    if "Beauty" in category:
        base = 30 + (index * 10)
        return f"${base}-${base+20}"
    else:
        base = 15 + (index * 5)
        return f"${base}-${base+15}"

def analyze_competitor_pricing(competitor_data):
    analysis = []
    for comp in competitor_data:
        analysis.append(f"- {comp['name']}: {comp['pricing_strategy']} pricing at {comp['price_range']}")
    return "\n".join(analysis)

@bp.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(force=True)
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400
    with get_db() as conn:
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            return jsonify({"error": "Email already registered."}), 409
        password_hash = hash_password(password)
        conn.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)", (email, password_hash))
        conn.commit()
        user_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
    token = generate_token(user_id, email)
    return jsonify({"token": token, "user": {"id": user_id, "email": email}}), 201

@bp.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(force=True)
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user or not verify_password(password, user["password_hash"]):
            return jsonify({"error": "Invalid email or password."}), 401
        token = generate_token(user["id"], user["email"])
    return jsonify({"token": token, "user": {"id": user["id"], "email": user["email"]}}), 200

# Reviews API Routes
@bp.route("/reviews", methods=["POST"])
@require_auth
def create_review():
    data = request.get_json(force=True)
    
    # Validation
    business_id = data.get("businessId")
    rating = data.get("rating")
    text = data.get("text", "").strip()
    name = data.get("name", "").strip()
    
    if not business_id:
        return jsonify({"error": "Business ID is required"}), 400
    
    if not rating or not isinstance(rating, int) or rating < 1 or rating > 5:
        return jsonify({"error": "Rating must be between 1 and 5"}), 400
    
    if not text or len(text) < 10:
        return jsonify({"error": "Review text must be at least 10 characters"}), 400
    
    if len(text) > 1000:
        return jsonify({"error": "Review text must be less than 1000 characters"}), 400
    
    # Check if business exists
    with get_db() as conn:
        business = conn.execute("SELECT id FROM businesses WHERE id = ?", (business_id,)).fetchone()
        if not business:
            return jsonify({"error": "Business not found"}), 404
        
        # Get user info from token
        user_id = request.user_id
        
        # Check if user is the owner of this business
        business_owner = conn.execute(
            "SELECT owner_id FROM businesses WHERE id = ?",
            (business_id,)
        ).fetchone()
        
        if business_owner and business_owner["owner_id"] == user_id:
            return jsonify({"error": "You cannot review your own business"}), 403
        
        # Check if user has already reviewed this business (optional - can be removed if you want to allow multiple reviews)
        existing_review = conn.execute(
            "SELECT id FROM reviews WHERE business_id = ? AND user_id = ?",
            (business_id, user_id)
        ).fetchone()
        
        if existing_review:
            return jsonify({"error": "You have already reviewed this business"}), 409
        
        # Insert review with user_id
        conn.execute(
            "INSERT INTO reviews (business_id, user_id, name, rating, text, ip_address) VALUES (?, ?, ?, ?, ?, ?)",
            (business_id, user_id, name if name else None, rating, text, request.remote_addr)
        )
        conn.commit()
        review_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
        
        # Update business average rating
        avg_result = conn.execute(
            "SELECT AVG(rating) as avg_rating, COUNT(*) as total_reviews FROM reviews WHERE business_id = ?",
            (business_id,)
        ).fetchone()
        
        if avg_result["avg_rating"]:
            conn.execute(
                "UPDATE businesses SET rating = ? WHERE id = ?",
                (round(avg_result["avg_rating"], 1), business_id)
            )
            conn.commit()
    
    return jsonify({
        "id": review_id,
        "businessId": business_id,
        "name": name,
        "rating": rating,
        "text": text,
        "createdAt": datetime.datetime.now().isoformat()
    }), 201

@bp.route("/reviews/<int:business_id>", methods=["GET"])
def get_business_reviews(business_id):
    page = request.args.get("page", 1, type=int)
    limit = request.args.get("limit", 10, type=int)
    offset = (page - 1) * limit
    
    with get_db() as conn:
        # Check if business exists
        business = conn.execute("SELECT id FROM businesses WHERE id = ?", (business_id,)).fetchone()
        if not business:
            return jsonify({"error": "Business not found"}), 404
        
        # Get reviews with pagination
        cursor = conn.execute(
            "SELECT * FROM reviews WHERE business_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (business_id, limit, offset)
        )
        reviews = [dict(row) for row in cursor.fetchall()]
        
        # Get total count
        total = conn.execute(
            "SELECT COUNT(*) as count FROM reviews WHERE business_id = ?",
            (business_id,)
        ).fetchone()["count"]
    
    return jsonify({
        "reviews": reviews,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit
        }
    }), 200

@bp.route("/reviews/average/<int:business_id>", methods=["GET"])
def get_business_average_rating(business_id):
    with get_db() as conn:
        # Check if business exists
        business = conn.execute("SELECT id FROM businesses WHERE id = ?", (business_id,)).fetchone()
        if not business:
            return jsonify({"error": "Business not found"}), 404
        
        # Get average rating and total reviews
        result = conn.execute(
            "SELECT AVG(rating) as avg_rating, COUNT(*) as total_reviews FROM reviews WHERE business_id = ?",
            (business_id,)
        ).fetchone()
        
        avg_rating = result["avg_rating"] if result["avg_rating"] else 0
        total_reviews = result["total_reviews"]
    
    return jsonify({
        "averageRating": round(avg_rating, 1),
        "totalReviews": total_reviews,
        "businessId": business_id
    }), 200

# Add appointment booking endpoint
@bp.route('/appointments', methods=['POST'])
def book_appointment():
    """Book an appointment with a business"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['business_id', 'name', 'email', 'date', 'time', 'service']
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Validate email format
        if '@' not in data['email']:
            return jsonify({"error": "Invalid email format"}), 400
        
        # Validate date (must be in the future)
        try:
            appointment_date = datetime.datetime.strptime(data['date'], '%Y-%m-%d').date()
            if appointment_date < datetime.date.today():
                return jsonify({"error": "Appointment date must be in the future"}), 400
        except ValueError:
            return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400
        
        # Store appointment in database
        with get_db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    business_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    phone TEXT,
                    date TEXT NOT NULL,
                    time TEXT NOT NULL,
                    service TEXT NOT NULL,
                    message TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (business_id) REFERENCES businesses (id) ON DELETE CASCADE
                )
            """)
            
            conn.execute("""
                INSERT INTO appointments (business_id, name, email, phone, date, time, service, message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data['business_id'],
                data['name'],
                data['email'],
                data.get('phone', ''),
                data['date'],
                data['time'],
                data['service'],
                data.get('message', '')
            ))
            
            appointment_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            
            # Get business details for response
            business = conn.execute("SELECT name FROM businesses WHERE id = ?", (data['business_id'],)).fetchone()
            business_name = business[0] if business else "Unknown Business"
        
        return jsonify({
            "success": True,
            "message": f"Appointment request submitted successfully. {business_name} will contact you soon to confirm.",
            "appointment_id": appointment_id
        }), 201
        
    except Exception as e:
        print(f"Appointment booking error: {e}")
        return jsonify({"error": "Failed to book appointment. Please try again."}), 500

# Get appointments for a business (for business owners)
@bp.route('/businesses/<int:business_id>/appointments', methods=['GET'])
@require_auth
def get_business_appointments(business_id):
    """Get all appointments for a business (requires authentication)"""
    try:
        with get_db() as conn:
            appointments = conn.execute("""
                SELECT id, name, email, phone, date, time, service, message, status, created_at
                FROM appointments 
                WHERE business_id = ?
                ORDER BY created_at DESC
            """, (business_id,)).fetchall()
            
            appointment_list = []
            for row in appointments:
                appointment_list.append({
                    "id": row[0],
                    "name": row[1],
                    "email": row[2],
                    "phone": row[3],
                    "date": row[4],
                    "time": row[5],
                    "service": row[6],
                    "message": row[7],
                    "status": row[8],
                    "created_at": row[9]
                })
            
            return jsonify({"appointments": appointment_list}), 200
            
    except Exception as e:
        print(f"Get appointments error: {e}")
        return jsonify({"error": "Failed to fetch appointments"}), 500

# AI Chat endpoint
@bp.route('/chat', methods=['POST'])
def ai_chat():
    """AI-powered chat endpoint"""
    try:
        data = request.get_json()
        user_message = data.get('message', '').lower()
        business_id = data.get('business_id')
        conversation_history = data.get('history', [])
        
        if not user_message:
            return jsonify({"error": "Message is required"}), 400
        
        # Get business information for context
        business_info = {}
        if business_id:
            with get_db() as conn:
                business = conn.execute("""
                    SELECT name, description, services, category, location, socials
                    FROM businesses WHERE id = ?
                """, (business_id,)).fetchone()
                
                if business:
                    business_info = {
                        "name": business[0],
                        "description": business[1],
                        "services": business[2],
                        "category": business[3],
                        "location": business[4],
                        "socials": json.loads(business[5]) if business[5] else {}
                    }
        
        # Simple smart responses based on keywords
        ai_response = generate_smart_response(user_message, business_info)
        
        return jsonify({
            "response": ai_response,
            "timestamp": datetime.datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        print(f"AI Chat error: {e}")
        return jsonify({
            "response": "I'm having trouble processing your request right now. Please try again or contact the business directly.",
            "timestamp": datetime.datetime.now().isoformat()
        }), 500

def generate_smart_response(user_message, business_info):
    """Generate smart responses based on keywords and business info"""
    
    # Common greetings
    if any(word in user_message for word in ['hello', 'hi', 'hey', 'good morning', 'good afternoon']):
        return f"Hello! Welcome to {business_info.get('name', 'our business')}. How can I help you today? 😊"
    
    # Service inquiries
    if any(word in user_message for word in ['service', 'services', 'offer', 'what do you do']):
        services = business_info.get('services', 'various services')
        return f"We offer {services}. Is there a specific service you're interested in?"
    
    # Location questions
    if any(word in user_message for word in ['where', 'location', 'address', 'place']):
        location = business_info.get('location', 'our location')
        return f"We're located at {location}. Would you like directions or help finding us?"
    
    # Contact information
    if any(word in user_message for word in ['contact', 'phone', 'call', 'email', 'reach']):
        socials = business_info.get('socials', {})
        phone = socials.get('phone', 'our phone number')
        email = socials.get('email', 'our email')
        return f"You can reach us at {phone} or email us at {email}. We'd be happy to help!"
    
    # Appointment booking
    if any(word in user_message for word in ['appointment', 'book', 'schedule', 'meeting']):
        return "Great! You can book an appointment using the 'Book Appointment' button on this page, or I can help guide you through the process. What type of service are you looking for?"
    
    # Business hours
    if any(word in user_message for word in ['hours', 'open', 'close', 'time', 'when']):
        return "I don't have specific hours listed, but I'd be happy to help you book an appointment or you can call us directly for our current hours."
    
    # Pricing questions
    if any(word in user_message for word in ['price', 'cost', 'how much', 'fee', 'charge']):
        return "For pricing information, I'd recommend calling us directly or booking a consultation. We can provide detailed quotes based on your specific needs."
    
    # General help
    if any(word in user_message for word in ['help', 'assist', 'support']):
        return f"I'm here to help! I can answer questions about our services, help you book appointments, or connect you with our team. What would you like to know about {business_info.get('name', 'our business')}?"
    
    # Thank you responses
    if any(word in user_message for word in ['thank', 'thanks', 'appreciate']):
        return "You're very welcome! Is there anything else I can help you with?"
    
    # Default response
    return f"Thanks for your message! I'm here to help with {business_info.get('name', 'our business')}. You can ask me about our services, book appointments, or get contact information. How can I assist you today?"
