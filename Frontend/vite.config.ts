import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const proxyTarget = env.VITE_DEV_PROXY_TARGET || "http://backend:8000";
  const directProxyPaths = [
    "/auth",
    "/attendance",
    "/departments",
    "/events",
    "/face",
    "/health",
    "/login",
    "/media",
    "/programs",
    "/public-attendance",
    "/school-settings",
    "/users",
  ];
  const directProxyEntries = Object.fromEntries(
    directProxyPaths.map((path) => [
      path,
      {
        target: proxyTarget,
        changeOrigin: true,
      },
    ])
  );

  return {
    plugins: [react()],
    build: {
      rollupOptions: {
        output: {
          manualChunks: {
            react: ["react", "react-dom", "react-router-dom"],
            chartjs: ["chart.js", "react-chartjs-2"],
            recharts: ["recharts"],
            ui: ["react-icons", "react-modal", "bootstrap"],
          },
        },
      },
    },
    server: {
      host: "0.0.0.0",
      allowedHosts: true,
      proxy: {
        ...directProxyEntries,
        "/openapi.json": {
          target: proxyTarget,
          changeOrigin: true,
        },
        "/docs": {
          target: proxyTarget,
          changeOrigin: true,
        },
        "/redoc": {
          target: proxyTarget,
          changeOrigin: true,
        },
        "/api/docs": {
          target: proxyTarget,
          changeOrigin: true,
          rewrite: () => "/docs",
        },
        "/api/redoc": {
          target: proxyTarget,
          changeOrigin: true,
          rewrite: () => "/redoc",
        },
        "/api/openapi.json": {
          target: proxyTarget,
          changeOrigin: true,
          rewrite: () => "/openapi.json",
        },
        "/token": {
          target: proxyTarget,
          changeOrigin: true,
        },
        "/api": {
          target: proxyTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
