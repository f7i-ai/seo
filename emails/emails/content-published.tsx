import {
  Body,
  Container,
  Head,
  Heading,
  Html,
  Link,
  Preview,
  Section,
  Text,
} from "@react-email/components";
import * as React from "react";

interface ContentPublishedEmailProps {
  title?: string;
  url?: string;
  publishDate?: string;
}

export const ContentPublishedEmail = ({
  title = "Your Content",
  url = "https://f7i.ai",
  publishDate = new Date().toLocaleDateString(),
}: ContentPublishedEmailProps) => (
  <Html>
    <Head />
    <Preview>Your content has been published successfully!</Preview>
    <Body style={main}>
      <Container style={container}>
        <Heading style={h1}>Content Published!</Heading>
        <Text style={text}>
          Your content <strong>{title}</strong> has been successfully published.
        </Text>
        <Section style={infoSection}>
          <Text style={infoText}>
            <strong>Title:</strong> {title}
          </Text>
          <Text style={infoText}>
            <strong>Published:</strong> {publishDate}
          </Text>
        </Section>
        <Link href={url} style={button}>
          View Content
        </Link>
        <Text style={footer}>
          This is an automated notification from your SEO content generator.
        </Text>
      </Container>
    </Body>
  </Html>
);

export default ContentPublishedEmail;

const main = {
  backgroundColor: "#f6f9fc",
  fontFamily:
    '-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Oxygen-Sans,Ubuntu,Cantarell,"Helvetica Neue",sans-serif',
};

const container = {
  margin: "0 auto",
  padding: "20px 0 48px",
  maxWidth: "560px",
  backgroundColor: "#ffffff",
};

const h1 = {
  color: "#333",
  fontSize: "24px",
  fontWeight: "bold",
  margin: "40px 0",
  padding: "0",
};

const text = {
  color: "#333",
  fontSize: "16px",
  lineHeight: "26px",
  marginBottom: "16px",
};

const infoSection = {
  backgroundColor: "#f4f4f4",
  borderRadius: "8px",
  padding: "16px",
  margin: "24px 0",
};

const infoText = {
  color: "#333",
  fontSize: "14px",
  lineHeight: "24px",
  margin: "4px 0",
};

const button = {
  backgroundColor: "#0070f3",
  borderRadius: "5px",
  color: "#fff",
  display: "inline-block",
  fontSize: "16px",
  fontWeight: "bold",
  textDecoration: "none",
  textAlign: "center" as const,
  padding: "12px 20px",
  margin: "24px 0",
};

const footer = {
  color: "#898989",
  fontSize: "12px",
  lineHeight: "22px",
  marginTop: "24px",
};

