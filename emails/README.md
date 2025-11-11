# React Email Templates

This directory contains email templates built with [React Email](https://react.email).

## Getting Started

### Development

Run the development server to preview your email templates:

```bash
npm run dev
```

This will start the React Email dev server at `http://localhost:3000` where you can preview and test your templates.

### Export Templates

Export your templates to HTML:

```bash
npm run export
```

This will generate static HTML files from your React components.

## Available Templates

- **welcome.tsx** - Welcome email for new users
- **content-published.tsx** - Notification when SEO content is published
- **product-update.tsx** - Factory AI product updates with numbered features and coming soon section

## Creating New Templates

1. Create a new `.tsx` file in the `emails/` directory
2. Import components from `@react-email/components`
3. Export your email component
4. View it in the dev server

Example:

```tsx
import { Html, Button } from "@react-email/components";

export const MyEmail = () => (
  <Html>
    <Button href="https://example.com">
      Click me
    </Button>
  </Html>
);

export default MyEmail;
```

## Documentation

For more information, visit [react.email/docs](https://react.email/docs/introduction)

