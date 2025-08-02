# SFBiz - Business Directory & Management Platform

A comprehensive business directory and management platform built with **Next.js** (frontend) and **Flask** (backend), featuring advanced authentication, Google Maps integration, AI-powered chat support, and dynamic pricing analysis.

## 🚀 Features

### 🔐 Authentication & Security
- **JWT-based authentication** with secure token management
- **Password hashing** using bcrypt
- **Protected routes** for business owners
- **Session management** with localStorage

### 🏢 Business Management
- **Business registration and profiles** with detailed information
- **Image gallery** with file upload support (PNG, JPG, GIF, WebP)
- **Google Maps integration** with geocoding
- **Social media links** (Instagram, Facebook, X, LinkedIn, Website, Phone, Email)
- **Business hours management**
- **Owner verification** and access control

### 💬 Advanced Communication
- **AI-powered live chat** with smart responses
- **Appointment booking system** with form validation
- **In-app calling** integration
- **Real-time customer support**

### 🎯 AI-Powered Features
- **Smart chat responses** based on business context
- **Service recommendations** using AI analysis
- **Dynamic pricing analysis** with market insights
- **Competitor analysis** and market positioning
- **Revenue optimization** suggestions

### 🔍 Search & Discovery
- **Advanced search** with multiple filters
- **Category-based filtering** with emoji indicators
- **Rating and review system**
- **Location-based search**

### 📊 Analytics & Insights
- **Business performance tracking**
- **Market analysis** and competitor insights
- **Pricing strategy recommendations**
- **Revenue optimization tools**

## 🛠️ Tech Stack

### Frontend
- **Next.js 14** - React framework
- **TypeScript** - Type safety
- **Tailwind CSS** - Styling
- **Framer Motion** - Animations
- **React Icons** - Icon library
- **Lucide React** - Additional icons

### Backend
- **Flask** - Python web framework
- **SQLite** - Database
- **JWT** - Authentication
- **bcrypt** - Password hashing
- **Google Maps API** - Geocoding
- **OpenAI API** - AI features (optional)

## 📁 Project Structure

```
SFbizFinal/
├── SFBizbck/                 # Backend (Flask)
│   ├── app.py               # Main Flask app
│   ├── routes.py            # API endpoints
│   ├── db.py               # Database setup
│   ├── requirements.txt     # Python dependencies
│   └── businesses.db       # SQLite database
├── sfbizfrnt/              # Frontend (Next.js)
│   ├── app/                # Next.js app directory
│   │   ├── page.tsx        # Home page
│   │   ├── login/          # Authentication pages
│   │   ├── register/
│   │   ├── add/            # Add business form
│   │   └── business/[id]/  # Business detail pages
│   ├── components/         # React components
│   ├── types/             # TypeScript definitions
│   └── package.json       # Node.js dependencies
└── README.md              # This file
```

## 🚀 Quick Start

### Prerequisites
- **Node.js** (v18 or higher)
- **Python** (v3.8 or higher)
- **Git**

### Backend Setup
```bash
# Navigate to backend directory
cd SFBizbck

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start Flask server
python app.py
```

### Frontend Setup
```bash
# Navigate to frontend directory
cd sfbizfrnt

# Install dependencies
npm install

# Start development server
npm run dev
```

### Environment Variables

Create `.env.local` in the frontend directory:
```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:5000
```

Create `.env` in the backend directory (optional):
```env
SECRET_KEY=your-secret-key-here
GOOGLE_MAPS_API_KEY=your-google-maps-api-key
OPENAI_API_KEY=your-openai-api-key
```

## 🔧 API Endpoints

### Authentication
- `POST /auth/register` - User registration
- `POST /auth/login` - User login

### Businesses
- `GET /businesses` - List all businesses
- `POST /businesses` - Add new business
- `GET /businesses/<id>` - Get business details
- `PATCH /businesses/<id>` - Update business
- `DELETE /businesses/<id>` - Delete business

### Images
- `POST /businesses/<id>/images` - Upload image
- `GET /businesses/<id>/images` - Get business images
- `DELETE /businesses/<id>/images/<image_id>` - Delete image

### Communication
- `POST /chat` - AI chat endpoint
- `POST /appointments` - Book appointment
- `GET /businesses/<id>/appointments` - Get appointments

### AI Features
- `GET /businesses/<id>/ai-recommendations` - Service recommendations
- `GET /businesses/<id>/pricing-analysis` - Pricing analysis
- `POST /businesses/<id>/dynamic-pricing` - Set dynamic pricing

## 🎨 UI/UX Features

### Modern Design
- **Responsive design** for all devices
- **Dark/light mode** support
- **Smooth animations** with Framer Motion
- **Intuitive navigation** with clear visual hierarchy

### User Experience
- **Progressive disclosure** for complex forms
- **Real-time feedback** for user actions
- **Loading states** and error handling
- **Accessibility** features

### Business Owner Features
- **Dashboard** for business management
- **Analytics** and insights
- **Customer communication** tools
- **Revenue optimization** suggestions

## 🔒 Security Features

- **JWT token authentication**
- **Password hashing** with bcrypt
- **Protected API endpoints**
- **Input validation** and sanitization
- **CORS configuration** for development

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Next.js** team for the amazing framework
- **Flask** community for the Python web framework
- **Tailwind CSS** for the utility-first CSS framework
- **OpenAI** for AI capabilities
- **Google Maps** for location services

## 📞 Support

For support, email support@sfbiz.com or create an issue in this repository.

---

**Built with ❤️ for the business community** 