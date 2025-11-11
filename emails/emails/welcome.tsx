import {
  Body,
  Container,
  Head,
  Heading,
  Html,
  Link,
  Preview,
  Text,
} from "@react-email/components";
import * as React from "react";

interface WelcomeEmailProps {
  username?: string;
}

export const WelcomeEmail = ({
  username = "there",
}: WelcomeEmailProps) => (
  <Html>
    <Head />
    <Preview>Welcome to our platform!</Preview>
    <Body style={main}>
      <Container style={container}>
        <Heading style={h1}>Welcome, {username}!</Heading>
        <Text style={text}>
          Thank you for joining us. We're excited to have you on board.
        </Text>
        <Text style={text}>
          Get started by exploring our platform and discovering all the features
          we have to offer.
        </Text>
        <Link href="https://f7i.ai" style={link}>
          Get Started
        </Link>
        <Text style={footer}>
          If you didn't create this account, you can safely ignore this email.
        </Text>
      </Container>
    </Body>
  </Html>
);

export default WelcomeEmail;

const main = {
  backgroundColor: "#ffffff",
  fontFamily:
    '-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Oxygen-Sans,Ubuntu,Cantarell,"Helvetica Neue",sans-serif',
};

const container = {
  margin: "0 auto",
  padding: "20px 0 48px",
  maxWidth: "560px",
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
};

const link = {
  color: "#0070f3",
  fontSize: "16px",
  textDecoration: "underline",
};

const footer = {
  color: "#898989",
  fontSize: "12px",
  lineHeight: "22px",
  marginTop: "12px",
};

