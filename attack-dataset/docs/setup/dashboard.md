# OpsecAI Dashboard Setup Guide

The OpsecAI Dashboard is built with **Next.js 16**, **React 19**, and **Tailwind CSS 4**. It provides a modern, responsive interface for monitoring attack patterns, managing red team operations, and analyzing security data.

## Prerequisites

- Node.js 18+ 
- npm or yarn package manager
- Access to OpsecAI backend services

## Installation

### 1. Install Dependencies

```bash
cd frontend/dashboard
npm install
```

### 2. Environment Configuration

Create a `.env.local` file in the dashboard directory:

```bash
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:3001
NEXT_PUBLIC_WS_URL=ws://localhost:3001

# Feature Flags
NEXT_PUBLIC_ENABLE_ANALYTICS=true
NEXT_PUBLIC_ENABLE_REALTIME=true
```

## Available Scripts

### `npm run dev`

Starts the development server with hot-reload.
- Open [http://localhost:3000](http://localhost:3000) to view the dashboard
- The page will automatically reload when you make changes
- TypeScript and ESLint errors will appear in the console

### `npm run build`

Creates an optimized production build in the `.next` directory.
- Compiles TypeScript and optimizes React components
- Generates static pages and server-side rendering bundles
- Minifies JavaScript and CSS
- Ready for deployment

### `npm start`

Starts the production server (requires running `npm run build` first).
- Serves the optimized production build
- Runs on port 3000 by default
- For production deployments

### `npm run lint`

Runs ESLint to check code quality and find potential issues.
- Checks TypeScript and React code
- Enforces coding standards
- Helps maintain code quality

## Project Structure

```
frontend/dashboard/
├── app/                    # Next.js App Router
│   ├── dashboard/         # Dashboard pages
│   ├── layout.tsx         # Root layout
│   └── page.tsx           # Home page
├── components/            # React components
│   ├── attack-monitoring/ # Attack monitoring components
│   ├── auth/             # Authentication components
│   └── services/         # Service management components
├── lib/                  # Utility libraries
│   ├── auth.ts          # Authentication utilities
│   ├── persistence.ts   # State persistence
│   └── serviceMonitor.ts # Service monitoring
├── public/              # Static assets
└── package.json         # Dependencies and scripts
```

## Key Features

### Real-time Dashboard
- Live attack monitoring with WebSocket updates
- Service health status and metrics
- Real-time alerts and notifications

### Attack Monitoring
- Attack tree visualization with MITRE ATT&CK mapping
- Feedback loop analytics and adaptation tracking
- Session management for red team operations
- Historical analysis and trend detection

### Service Management
- Service health monitoring with auto-restart capabilities
- Performance metrics and response time tracking
- Advanced controls with cache statistics
- Real-time service status updates

### Authentication & Security
- JWT-based authentication
- Protected routes with role-based access
- Session persistence and management
- OpSec-aware UI components

### Advanced Analytics
- Export capabilities for reports and data
- Collaboration features for team operations
- Configurable alert thresholds
- Multi-format data export (JSON, CSV, PDF)

## Development Workflow

### Adding New Components

1. Create component in appropriate directory:
```bash
# Example: Create new monitoring component
mkdir -p components/attack-monitoring
touch components/attack-monitoring/NewComponent.tsx
```

2. Use shadcn/ui components for consistency:
```bash
npx shadcn@latest add button
npx shadcn@latest add card
```

3. Follow TypeScript best practices with proper typing

### Adding New Pages

1. Create page in `app/` directory:
```bash
# Example: Create new analytics page
mkdir -p app/analytics
touch app/analytics/page.tsx
```

2. Use Next.js App Router conventions
3. Implement proper error handling and loading states

### API Integration

Use the centralized API client pattern:

```typescript
// lib/api.ts
export async function fetchAttackData() {
  const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/attacks`);
  if (!response.ok) throw new Error('Failed to fetch data');
  return response.json();
}
```

## Styling

The dashboard uses **Tailwind CSS 4** for styling:

```typescript
// Example component with Tailwind
<div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
  <h2 className="text-xl font-bold text-gray-900 dark:text-white">
    Dashboard Title
  </h2>
</div>
```

### Dark Mode

The dashboard supports dark mode through CSS variables and Tailwind's dark mode modifier:

```typescript
// Toggle dark mode
const toggleDarkMode = () => {
  document.documentElement.classList.toggle('dark');
};
```

## WebSocket Integration

Real-time updates use WebSocket connections:

```typescript
// lib/websocket.ts
export function createWebSocketConnection(url: string) {
  const ws = new WebSocket(url);
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    // Handle real-time updates
  };
  
  return ws;
}
```

## Performance Optimization

### Code Splitting
Next.js automatically splits code by routes. Use dynamic imports for additional splitting:

```typescript
const HeavyComponent = dynamic(() => import('./HeavyComponent'), {
  loading: () => <LoadingSpinner />,
  ssr: false
});
```

### Image Optimization
Use Next.js Image component for automatic optimization:

```typescript
import Image from 'next/image';

<Image 
  src="/logo.png" 
  alt="Logo" 
  width={200} 
  height={50}
  priority
/>
```

## Troubleshooting

### Port Already in Use
```bash
# Kill process on port 3000
npx kill-port 3000
# Or use different port
npm run dev -- -p 3001
```

### Build Errors
```bash
# Clear Next.js cache
rm -rf .next
# Reinstall dependencies
rm -rf node_modules package-lock.json
npm install
```

### TypeScript Errors
```bash
# Regenerate TypeScript types
npx tsc --noEmit
```

## Deployment

### Production Build
```bash
npm run build
npm start
```

### Docker Deployment
```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
```

### Environment Variables for Production
Ensure all required environment variables are set in your production environment:
- `NEXT_PUBLIC_API_URL`
- `NEXT_PUBLIC_WS_URL`
- Any API keys or authentication tokens

## Browser Support

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

## Contributing

When contributing to the dashboard:
1. Follow TypeScript best practices
2. Use Tailwind CSS for styling
3. Implement proper error handling
4. Add loading states for async operations
5. Test responsive design on multiple screen sizes
6. Follow the existing component structure

## Support

For issues or questions:
1. Check the browser console for error messages
2. Verify backend services are running
3. Ensure environment variables are properly configured
4. Review the Next.js documentation: https://nextjs.org/docs

---

**Dashboard Version:** 1.0.0  
**Framework:** Next.js 16.2.6  
**React Version:** 19.2.4  
**Last Updated:** 2026-05-19