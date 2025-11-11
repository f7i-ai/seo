import {
  Body,
  Container,
  Head,
  Html,
  Img,
  Link,
  Section,
  Text,
  Row,
  Column,
} from "@react-email/components";
import { Linkedin } from "lucide-react";
import * as React from "react";

interface UpdateItem {
  number: number;
  title: string;
  description: string;
}

interface ProductUpdateEmailProps {
  updates?: UpdateItem[];
  ctaText?: string;
  ctaUrl?: string;
  showComingSoon?: boolean;
  domain?: string;
  unsubscribeUrl?: string;
}

export const ProductUpdateEmail = ({
  updates = [
    {
      number: 1,
      title: "Factory AI Agent",
      description:
        "Eliminate hours of manual data entry and scheduling. AI automatically creates assets, plans maintenance, and prioritizes work based on your equipment's real condition. Spend your time fixing problems, not filling out forms.",
    },
    {
      number: 2,
      title: "Bulk Updates",
      description:
        "Stop updating assets one at a time. Bulk edit hundreds of work orders and equipment records instantly. Hours of repetitive work, done in seconds.",
    },
    {
      number: 3,
      title: "Voice-Enabled Work Orders",
      description:
        "Stop pulling off gloves to type. Speak your updates in any language and AI handles the rest. Create work orders, update asset status, all hands-free on the factory floor.",
    },
    {
      number: 4,
      title: "What's Next?",
      description:
        "Anomaly alerts without context are useless. Now ask AI follow-up questions: \"What's causing this spike?\" \"When did it start?\" \"Any similar failures?\" Get instant answers instead of digging through data for hours. No more static reports—ask dynamic questions and get real-time insights tailored to your exact situation.",
    },
  ],
  ctaText = "Get Started",
  ctaUrl = "https://app.f7i.ai",
  showComingSoon = false,
  domain = "{{domain}}",
  unsubscribeUrl = "{{amazonSESUnsubscribeUrl}}",
}: ProductUpdateEmailProps) => (
  <Html lang="en">
    <Head>
      <style>{`
        @media (prefers-color-scheme: dark) {
          .dark-mode-bg { background-color: #0a0a0a !important; }
          .dark-mode-text { color: #ffffff !important; }
          .dark-mode-text-gray { color: #a0a0a0 !important; }
          .dark-mode-text-muted { color: #666666 !important; }
          .dark-mode-card { 
            background: linear-gradient(to bottom, #1a1a1a, #0f0f0f) !important;
            border: 1px solid #262626 !important;
          }
          .dark-mode-border { border-color: #262626 !important; }
          .dark-mode-logo-border { border-color: #333333 !important; }
        }
        @media only screen and (max-width: 600px) {
          .update-card-mobile {
            background: transparent !important;
            border: none !important;
            padding: 0 !important;
            box-shadow: none !important;
            margin-bottom: 32px !important;
          }
          .content-mobile {
            padding: 0 16px !important;
          }
        }
      `}</style>
    </Head>
    <Body style={main}>
      <Container style={container}>
        {/* Header */}
        <Section style={header}>
          <div style={logoContainer}>
            <div
              style={{
                display: "inline-block",
                padding: "4px",
                border: "1px solid #d1d5db",
                borderRadius: "4px",
              }}
            >
              <Img
                src="http://cdn.mcauto-images-production.sendgrid.net/9fd54d63e9989f76/7e3fb38f-97e0-47e4-953e-3cb893fa64b0/100x100.png"
                alt="Factory AI Logo"
                width="32"
                height="32"
              />
            </div>
          </div>
          <Text style={logoText}>Factory AI</Text>
          <Text style={tagline}>Stop downtime before it stops you</Text>
        </Section>

        {/* Hero Section */}
        <Section style={hero}>
          <Text style={heroTitle}>November Product Updates</Text>
          <Text style={heroDescription}>
            We have 4 new exciting updates
          </Text>
        </Section>

        {/* Product Updates */}
        <Section style={content} className="content-mobile">
          {updates.map((update, index) => (
            <div key={update.number}>
              <div style={updateCard} className="update-card-mobile">
                {index === 0 && (
                  <Img
                    src="http://cdn.mcauto-images-production.sendgrid.net/9fd54d63e9989f76/799ec221-4d94-4207-8872-fe8676dd9cf5/1536x1024.png"
                    alt="Factory AI Agent"
                    style={{
                      width: "100%",
                      height: "auto",
                      marginBottom: "20px",
                      borderRadius: "8px",
                      aspectRatio: "16/9",
                      objectFit: "cover",
                    }}
                  />
                )}
                {index === 1 && (
                  <Img
                    src="http://cdn.mcauto-images-production.sendgrid.net/9fd54d63e9989f76/59dc0f7a-6659-4741-80cc-2e8268abcb6f/1200x800.png"
                    alt="Bulk Updates"
                    style={{
                      width: "100%",
                      height: "auto",
                      marginBottom: "20px",
                      borderRadius: "8px",
                      aspectRatio: "16/9",
                      objectFit: "cover",
                    }}
                  />
                )}
                {index === 2 && (
                  <Img
                    src="http://cdn.mcauto-images-production.sendgrid.net/9fd54d63e9989f76/ea927869-9f63-4ae7-831a-b5dc1585a6fc/1024x1024.png"
                    alt="Voice-Enabled Work Orders"
                    style={{
                      width: "100%",
                      height: "auto",
                      marginBottom: "20px",
                      borderRadius: "8px",
                      aspectRatio: "16/9",
                      objectFit: "cover",
                    }}
                  />
                )}
                {index === 3 && (
                  <Img
                    src="http://cdn.mcauto-images-production.sendgrid.net/9fd54d63e9989f76/7336e12e-48ef-4d3a-9c34-cbe4643aa600/1200x400.png"
                    alt="Factory AI Predict"
                    style={{
                      width: "100%",
                      maxWidth: "600px",
                      height: "auto",
                      minHeight: "220px",
                      marginBottom: "28px",
                      marginTop: "8px",
                      borderRadius: "8px",
                      display: "block",
                    }}
                  />
                )}
                <div style={updateNumber}>{update.number}</div>
                <Text style={updateTitle}>{update.title}</Text>
                <Text style={updateDescription}>{update.description}</Text>
                {index < 2 && (
                  <Link href={domain} style={inlineCtaButton}>
                    Try it now →
                  </Link>
                )}
              </div>
            </div>
          ))}
        </Section>

        {/* Coming Soon Section */}
        {showComingSoon && (
          <Section style={comingSoon} className="update-card-mobile">
            <div style={comingSoonBadge}>Coming Soon</div>
            <Text style={comingSoonTitle}>
              Predict Agent: Your AI Vibration Analyst
            </Text>
            <Text style={comingSoonText}>
              <strong>Dynamic query engine:</strong> Ask natural language
              questions about asset performance, failure modes, and maintenance
              trends—get instant data-driven answers.
            </Text>
            <Text style={comingSoonText}>
              <strong>Anomaly detection:</strong> Real-time alerts for deviation
              from normal operating conditions. Catch bearing failures,
              misalignment, and imbalance before catastrophic failure.
            </Text>
            <Text style={comingSoonText}>
              <strong>AI-powered vibration analysis:</strong> Automated FFT
              analysis, trending, and root cause recommendations. Like having a
              Level III analyst monitoring every asset 24/7.
            </Text>
          </Section>
        )}

        {/* CTA */}
        <Section style={cta}>
          <Link href={ctaUrl} style={ctaButton}>
            Explore All Features
          </Link>
          <Text style={ctaSubtext}>
            Have questions?{" "}
            <Link href="mailto:support@f7i.ai" style={ctaLink}>
              Talk to our team
            </Link>
          </Text>
          
          {/* Stacked Avatars */}
          <div style={{ marginTop: "20px" }}>
            <Row style={{ width: "auto", margin: "0 auto", display: "inline-flex" }}>
              <Column
                style={{
                  width: "44px",
                  height: "44px",
                  padding: "0",
                  textAlign: "center" as const,
                  verticalAlign: "middle" as const,
                  lineHeight: "0",
                }}
              >
                <div
                  style={{
                    boxSizing: "border-box" as const,
                    height: "44px",
                    width: "44px",
                    overflow: "hidden",
                    borderRadius: "100%",
                    border: "4px solid #ffffff",
                    backgroundColor: "#0a0a0a",
                  }}
                >
                  <Img
                    src="http://cdn.mcauto-images-production.sendgrid.net/9fd54d63e9989f76/b38ac52b-d2d9-4b91-9adf-2205f31f63f5/800x800.png"
                    alt="Tim Cheung"
                    width="36"
                    height="36"
                    style={{
                      display: "inline-block",
                      height: "100%",
                      width: "100%",
                      objectFit: "cover" as const,
                    }}
                  />
                </div>
              </Column>
              <Column
                style={{
                  width: "44px",
                  height: "44px",
                  padding: "0",
                  textAlign: "center" as const,
                  verticalAlign: "middle" as const,
                  lineHeight: "0",
                  position: "relative" as const,
                  left: "-12px",
                }}
              >
                <div
                  style={{
                    boxSizing: "border-box" as const,
                    height: "44px",
                    width: "44px",
                    overflow: "hidden",
                    borderRadius: "100%",
                    border: "4px solid #ffffff",
                    backgroundColor: "#0a0a0a",
                  }}
                >
                  <Img
                    src="http://cdn.mcauto-images-production.sendgrid.net/9fd54d63e9989f76/f838943f-ae31-406a-b380-eea5c6bc1e84/427x640.png"
                    alt="Jean-Philippe Picard"
                    width="36"
                    height="36"
                    style={{
                      display: "inline-block",
                      height: "100%",
                      width: "100%",
                      objectFit: "cover" as const,
                    }}
                  />
                </div>
              </Column>
              <Column
                style={{
                  width: "44px",
                  height: "44px",
                  padding: "0",
                  textAlign: "center" as const,
                  verticalAlign: "middle" as const,
                  lineHeight: "0",
                  position: "relative" as const,
                  left: "-24px",
                }}
              >
                <div
                  style={{
                    boxSizing: "border-box" as const,
                    height: "44px",
                    width: "44px",
                    overflow: "hidden",
                    borderRadius: "100%",
                    border: "4px solid #ffffff",
                    backgroundColor: "#0a0a0a",
                  }}
                >
                  <Img
                    src="http://cdn.mcauto-images-production.sendgrid.net/9fd54d63e9989f76/a5f2bd44-126d-4402-b938-f309c745c1d3/200x200.png"
                    alt="Luka Gamulin"
                    width="36"
                    height="36"
                    style={{
                      display: "inline-block",
                      height: "100%",
                      width: "100%",
                      objectFit: "cover" as const,
                    }}
                  />
                </div>
              </Column>
              <Column
                style={{
                  width: "44px",
                  height: "44px",
                  padding: "0",
                  textAlign: "center" as const,
                  verticalAlign: "middle" as const,
                  lineHeight: "0",
                  position: "relative" as const,
                  left: "-36px",
                }}
              >
                <div
                  style={{
                    boxSizing: "border-box" as const,
                    height: "44px",
                    width: "44px",
                    overflow: "hidden",
                    borderRadius: "100%",
                    border: "4px solid #ffffff",
                    backgroundColor: "#0a0a0a",
                  }}
                >
                  <Img
                    src="http://cdn.mcauto-images-production.sendgrid.net/9fd54d63e9989f76/a4ddad75-30c6-405e-bc25-46264f8b0dc6/800x800.png"
                    alt="Alec Panetta"
                    width="36"
                    height="36"
                    style={{
                      display: "inline-block",
                      height: "100%",
                      width: "100%",
                      objectFit: "cover" as const,
                    }}
                  />
                </div>
              </Column>
            </Row>
          </div>
        </Section>

        {/* Footer */}
        <Section style={footer}>
          <div style={socialContainer}>
            <Link href="https://www.linkedin.com/company/factory-ai">
              <Linkedin size={20} color="#666666" />
            </Link>
          </div>
          
          <Text style={footerText}>
            Factory AI &copy; 2025. All rights reserved.
          </Text>
          <Text style={footerText}>
            <Link href={unsubscribeUrl} style={footerLink}>
              Unsubscribe
            </Link>
          </Text>
        </Section>
      </Container>
    </Body>
  </Html>
);

export default ProductUpdateEmail;

// Styles
const main = {
  fontFamily:
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif",
  backgroundColor: "#fcfcfd",
  color: "#0a0a0a",
  lineHeight: "1.6",
};

const container = {
  maxWidth: "600px",
  margin: "0 auto",
  backgroundColor: "#fcfcfd",
};

const header = {
  padding: "48px 32px 32px",
  textAlign: "center" as const,
};

const logoContainer = {
  marginBottom: "8px",
};

const logoImg = {
  width: "32px",
  height: "32px",
  padding: "4px",
  border: "1px solid #f3f4f6",
  borderRadius: "4px",
  display: "inline-block",
  filter: "brightness(0)",
};

const logoText = {
  fontSize: "24px",
  fontWeight: "600",
  color: "#0a0a0a",
  marginBottom: "8px",
  marginTop: "0",
};

const tagline = {
  fontSize: "14px",
  color: "#666666",
  margin: "0",
};

const hero = {
  padding: "0 32px 32px",
  textAlign: "center" as const,
};

const heroTitle = {
  fontSize: "32px",
  fontWeight: "600",
  color: "#0a0a0a",
  marginBottom: "16px",
  marginTop: "0",
  lineHeight: "1.2",
};

const heroDescription = {
  fontSize: "16px",
  color: "#525252",
  lineHeight: "1.5",
  margin: "0",
};

const productShowcase = {
  padding: "48px 32px",
  textAlign: "center" as const,
};

const stackedImagesContainer = {
  position: "relative" as const,
  maxWidth: "540px",
  margin: "0 auto",
  height: "380px",
};

const stackedImageWrapper = {
  position: "absolute" as const,
  top: "0",
  left: "50%",
  transform: "translateX(-50%) rotate(-3deg)",
  width: "85%",
  zIndex: "1",
};

const stackedImageBack = {
  width: "100%",
  height: "auto",
  borderRadius: "12px",
  border: "1px solid #000000",
  boxShadow: "0 20px 50px -12px rgba(0, 0, 0, 0.15), 0 8px 16px -8px rgba(0, 0, 0, 0.08)",
};

const stackedImageWrapperFront = {
  position: "absolute" as const,
  top: "50px",
  left: "50%",
  transform: "translateX(-50%) rotate(2deg)",
  width: "90%",
  zIndex: "2",
};

const stackedImageFront = {
  width: "100%",
  height: "auto",
  borderRadius: "12px",
  border: "1px solid #000000",
  boxShadow: "0 25px 60px -15px rgba(0, 0, 0, 0.2), 0 10px 20px -10px rgba(0, 0, 0, 0.1)",
};

const content = {
  padding: "0 32px",
};

const updateCard = {
  background: "#ffffff",
  border: "1px solid #e5e7eb",
  borderRadius: "16px",
  padding: "32px",
  marginBottom: "20px",
  boxShadow: "0 1px 3px 0 rgba(0, 0, 0, 0.02), 0 1px 2px 0 rgba(0, 0, 0, 0.03)",
};

const updateNumber = {
  display: "inline-block",
  width: "28px",
  height: "28px",
  background: "#000000",
  color: "#ffffff",
  borderRadius: "6px",
  textAlign: "center" as const,
  lineHeight: "28px",
  fontWeight: "700",
  fontSize: "13px",
  marginBottom: "14px",
};

const updateTitle = {
  fontSize: "22px",
  fontWeight: "700",
  color: "#111827",
  marginBottom: "12px",
  marginTop: "0",
  letterSpacing: "-0.02em",
};

const updateDescription = {
  fontSize: "15px",
  color: "#6b7280",
  lineHeight: "1.7",
  margin: "0",
};

const comingSoon = {
  background: "#ffffff",
  border: "1px solid #e5e7eb",
  borderRadius: "16px",
  padding: "32px",
  margin: "24px 32px",
  boxShadow: "0 1px 3px 0 rgba(0, 0, 0, 0.02), 0 1px 2px 0 rgba(0, 0, 0, 0.03)",
};

const comingSoonBadge = {
  display: "inline-block",
  background: "linear-gradient(135deg, #3ecf8e 0%, #2fb87c 100%)",
  color: "#ffffff",
  padding: "6px 14px",
  borderRadius: "8px",
  fontSize: "11px",
  fontWeight: "700",
  textTransform: "uppercase" as const,
  letterSpacing: "0.8px",
  marginBottom: "16px",
  boxShadow: "0 2px 8px rgba(62, 207, 142, 0.2)",
};

const comingSoonTitle = {
  fontSize: "22px",
  fontWeight: "700",
  color: "#111827",
  marginBottom: "12px",
  marginTop: "0",
  letterSpacing: "-0.02em",
};

const comingSoonText = {
  fontSize: "15px",
  color: "#6b7280",
  lineHeight: "1.7",
  marginBottom: "8px",
  marginTop: "0",
};

const cta = {
  textAlign: "center" as const,
  padding: "48px 32px",
};

const ctaButton = {
  display: "inline-block",
  background: "#000000",
  color: "#ffffff",
  padding: "12px 28px",
  borderRadius: "8px",
  textDecoration: "none",
  fontWeight: "700",
  fontSize: "14px",
  boxShadow: "0 4px 16px rgba(0, 0, 0, 0.25)",
};

const footer = {
  padding: "32px",
  textAlign: "center" as const,
  borderTop: "1px solid #d1d5db",
};

const footerText = {
  fontSize: "13px",
  color: "#999999",
  marginBottom: "8px",
  marginTop: "0",
};

const footerLink = {
  color: "#3ecf8e",
  textDecoration: "none",
  cursor: "pointer",
};

const socialContainer = {
  marginBottom: "16px",
};

const inlineCtaButton = {
  display: "inline-block",
  color: "#3ecf8e",
  fontSize: "14px",
  fontWeight: "600",
  textDecoration: "none",
  marginTop: "12px",
  transition: "opacity 0.3s ease",
};

const ctaSubtext = {
  fontSize: "14px",
  color: "#666666",
  marginTop: "16px",
  textAlign: "center" as const,
};

const ctaLink = {
  color: "#3ecf8e",
  textDecoration: "none",
  fontWeight: "600",
};

const avatarContainer = {
  display: "flex",
  justifyContent: "center",
  alignItems: "center",
  gap: "8px",
  marginTop: "24px",
};

const avatar = {
  borderRadius: "50%",
  border: "2px solid #ffffff",
  boxShadow: "0 2px 8px rgba(0, 0, 0, 0.1)",
};

