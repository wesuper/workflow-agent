import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import WebSocketProvider from "@/components/core/WebSocketProvider"; // Added
import { Toaster } from "react-hot-toast"; // Added

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "IM-Agent Control",
  description: "Control and monitor your IM-Agent",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${inter.className} bg-mech-primary text-mech-text-light`}>
        <WebSocketProvider> {/* Wrap content with WebSocketProvider */}
          {children}
        </WebSocketProvider>
        <Toaster
          position="bottom-right"
          toastOptions={{
            className: '',
            style: {
              background: '#333', // Dark background for toasts
              color: '#fff',       // Light text
              border: '1px solid #555',
            },
          }}
        /> {/* Added Toaster for notifications */}
      </body>
    </html>
  );
}
