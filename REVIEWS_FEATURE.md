# Reviews & Ratings Feature Documentation

## Overview

The Reviews & Ratings feature allows visitors to leave reviews and ratings on business pages within the SFBiz platform. This feature is fully responsive, user-friendly, and scalable.

## Features

### Frontend Components

1. **StarRating Component** (`components/StarRating.tsx`)
   - Interactive star rating system (1-5 stars)
   - Hover effects and click functionality
   - Accessible design with proper ARIA labels
   - Multiple sizes (sm, md, lg)
   - Support for both interactive and display-only modes

2. **ReviewForm Component** (`components/ReviewForm.tsx`)
   - Form for submitting new reviews
   - Real-time validation (10-1000 characters)
   - Character counter
   - Optional name field
   - Success/error message handling
   - Optimistic UI updates

3. **ReviewList Component** (`components/ReviewList.tsx`)
   - Displays reviews in chronological order (newest first)
   - Loading states with skeleton placeholders
   - Pagination with "Load More" functionality
   - Clean card layout with user avatars
   - Responsive design

4. **AverageRatingDisplay Component** (`components/AverageRatingDisplay.tsx`)
   - Shows business's average rating
   - Total review count
   - Rating distribution visualization
   - Color-coded rating text (Excellent, Good, etc.)

5. **ReviewsSection Component** (`components/ReviewsSection.tsx`)
   - Main container that combines all review components
   - Handles API calls and state management
   - SEO structured data (JSON-LD)
   - Optimistic updates

### Backend API Routes

1. **POST /api/reviews** (Requires Authentication)
   - Creates a new review
   - **Authentication Required**: Must be logged in with valid JWT token
   - Validation: rating (1-5), text (10-1000 chars)
   - One review per user per business (prevents duplicate reviews)
   - Updates business average rating automatically

2. **GET /api/reviews/:businessId**
   - Fetches reviews for a business
   - Pagination support (page, limit parameters)
   - Returns reviews with metadata

3. **GET /api/reviews/average/:businessId**
   - Gets average rating and total review count
   - Used for displaying rating summary

### Database Schema

```sql
CREATE TABLE reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    name TEXT,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    text TEXT NOT NULL,
    ip_address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES businesses (id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);
```

## Installation & Setup

### 1. Install Dependencies

```bash
# Frontend
cd sfbizfrnt
npm install lucide-react

# Backend dependencies are already included
```

### 2. Database Setup

The reviews table will be automatically created when the Flask app starts (see `SFBizbck/db.py`).

### 3. Environment Variables

Ensure your `.env.local` file has:
```
NEXT_PUBLIC_API_URL=http://localhost:5000
```

## Usage

### Adding Reviews to a Business Page

The ReviewsSection component is already integrated into the business page (`app/business/[id]/page.tsx`). It will automatically:

1. Display the business's average rating
2. Show a form for submitting new reviews
3. List existing reviews with pagination
4. Update the UI optimistically when reviews are submitted

### API Usage

```typescript
import { reviewsApi } from '@/lib/api';

// Submit a review
const review = await reviewsApi.createReview({
  businessId: 1,
  name: "John Doe",
  rating: 5,
  text: "Great service!"
});

// Get reviews for a business
const reviews = await reviewsApi.getBusinessReviews(1, 1, 10);

// Get average rating
const rating = await reviewsApi.getBusinessAverageRating(1);
```

## Security Features

1. **Authentication Required**
   - Users must be logged in to submit reviews
   - JWT token validation on backend
   - Frontend shows login prompt for unauthenticated users

2. **Input Validation**
   - Rating must be 1-5
   - Review text: 10-1000 characters
   - Name: optional, max 50 characters

3. **Duplicate Prevention**
   - One review per user per business
   - Prevents spam and duplicate submissions

4. **XSS Prevention**
   - Input sanitization on the backend
   - Proper HTML escaping

## SEO Features

1. **Structured Data**
   - JSON-LD schema markup for reviews
   - Includes aggregate rating and individual reviews
   - Helps search engines understand review content

2. **Review Schema**
   ```json
   {
     "@context": "https://schema.org",
     "@type": "LocalBusiness",
     "name": "Business Name",
     "aggregateRating": {
       "@type": "AggregateRating",
       "ratingValue": 4.5,
       "reviewCount": 10
     }
   }
   ```

## Responsive Design

- **Desktop**: Full-width layout with side-by-side components
- **Tablet**: Stacked layout with proper spacing
- **Mobile**: Optimized touch targets, stacked layout
- **Star Ratings**: Touch-friendly on mobile devices

## Performance Optimizations

1. **Optimistic Updates**
   - Reviews appear immediately after submission
   - Background API calls for data consistency

2. **Lazy Loading**
   - Reviews load in batches (10 per page)
   - "Load More" button for additional reviews

3. **Caching**
   - Reviews cached in component state
   - Average rating cached separately

## Future Enhancements

1. **Moderation System**
   - Admin panel for hiding inappropriate reviews
   - Report functionality for users

2. **Advanced Features**
   - Review helpfulness voting
   - Business owner responses
   - Review filtering by rating

3. **Analytics**
   - Track rating changes over time
   - Review submission analytics

## Testing

### Manual Testing Checklist

- [ ] Submit review with valid data (while logged in)
- [ ] Submit review with invalid data (should show errors)
- [ ] Try to submit review while not logged in (should show login prompt)
- [ ] Test star rating interaction
- [ ] Test character counter
- [ ] Test pagination
- [ ] Test mobile responsiveness
- [ ] Test authentication requirements
- [ ] Verify SEO structured data

### API Testing

```bash
# Test unauthorized review submission (should fail)
curl -X POST http://localhost:5000/reviews \
  -H "Content-Type: application/json" \
  -d '{"businessId": 1, "rating": 5, "text": "Great service!"}'

# Test authorized review submission
curl -X POST http://localhost:5000/reviews \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{"businessId": 1, "rating": 5, "text": "Great service!"}'

# Test getting reviews (public endpoint)
curl http://localhost:5000/reviews/1

# Test getting average rating (public endpoint)
curl http://localhost:5000/reviews/average/1
```

## Troubleshooting

### Common Issues

1. **Reviews not loading**
   - Check API URL in environment variables
   - Verify backend is running
   - Check browser console for errors

2. **Review submission fails**
   - Verify all required fields are filled
   - Check character limits
   - Ensure rating is between 1-5

3. **Star rating not working**
   - Check if lucide-react is installed
   - Verify component imports

### Debug Mode

Enable debug logging by adding to your component:
```typescript
console.log('API Response:', data);
```

## Contributing

When adding new features to the reviews system:

1. Follow the existing component structure
2. Add proper TypeScript types
3. Include error handling
4. Test on mobile devices
5. Update this documentation

## License

This feature is part of the SFBiz platform and follows the same licensing terms. 
This feature is part of the SFBiz platform and follows the same licensing terms. 