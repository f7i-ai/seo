import { render } from "@react-email/components";
import WelcomeEmail from "./emails/welcome";
import ContentPublishedEmail from "./emails/content-published";
import ProductUpdateEmail from "./emails/product-update";

/**
 * Render welcome email to HTML string
 */
export const renderWelcomeEmail = (username: string): string => {
  return render(<WelcomeEmail username={username} />);
};

/**
 * Render content published email to HTML string
 */
export const renderContentPublishedEmail = (
  title: string,
  url: string,
  publishDate?: string
): string => {
  return render(
    <ContentPublishedEmail 
      title={title} 
      url={url} 
      publishDate={publishDate}
    />
  );
};

/**
 * Render product update email to HTML string
 */
export const renderProductUpdateEmail = (
  updates?: Array<{ number: number; title: string; description: string }>,
  ctaText?: string,
  ctaUrl?: string,
  showComingSoon?: boolean
): string => {
  return render(
    <ProductUpdateEmail
      updates={updates}
      ctaText={ctaText}
      ctaUrl={ctaUrl}
      showComingSoon={showComingSoon}
    />
  );
};

export { WelcomeEmail, ContentPublishedEmail, ProductUpdateEmail };

