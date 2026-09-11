import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "TAIICO CRM",
    short_name: "TAIICO CRM",
    description: "Sistema de gestión para TAIICO Life Advisors",
    start_url: "/",
    display: "standalone",
    background_color: "#34587C",
    theme_color: "#34587C",
    lang: "es-MX",
    icons: [
      {
        src: "/logo.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/logo.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
