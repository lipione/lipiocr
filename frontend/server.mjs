import http from "node:http";
import { spawn } from "node:child_process";

const publicPort = Number(process.env.PORT || 3000);
const nextPort = Number(process.env.NEXT_INTERNAL_PORT || 3001);
const host = process.env.LIPIOCR_FRONTEND_HOST || "0.0.0.0";
const basePath = (process.env.NEXT_PUBLIC_BASE_PATH || "").replace(/\/$/, "");
const internalApiUrl = new URL(process.env.LIPIOCR_INTERNAL_API_BASE || "http://api:8000");

const next = spawn(
  "node",
  ["node_modules/next/dist/bin/next", "start", "--hostname", host, "--port", String(nextPort)],
  { stdio: "inherit", env: process.env },
);

next.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});

function stripBasePath(url) {
  if (!basePath || url === basePath || url.startsWith(`${basePath}/`)) {
    const stripped = basePath ? url.slice(basePath.length) || "/" : url;
    return stripped.startsWith("/") ? stripped : `/${stripped}`;
  }
  return url;
}

const server = http.createServer((request, response) => {
  const targetPath = stripBasePath(request.url || "/");
  const isApiRequest = targetPath === "/api" || targetPath.startsWith("/api/");
  const upstream = isApiRequest
    ? {
        host: internalApiUrl.hostname,
        port: Number(internalApiUrl.port || 80),
        path: `${internalApiUrl.pathname.replace(/\/$/, "")}${targetPath}`,
        label: "API",
      }
    : {
        host: "127.0.0.1",
        port: nextPort,
        path: targetPath,
        label: "Frontend",
      };

  const proxyRequest = http.request(
    {
      host: upstream.host,
      port: upstream.port,
      method: request.method,
      path: upstream.path,
      headers: request.headers,
    },
    (proxyResponse) => {
      response.writeHead(proxyResponse.statusCode || 502, proxyResponse.headers);
      proxyResponse.pipe(response);
    },
  );

  proxyRequest.on("error", (error) => {
    response.writeHead(502, { "content-type": "text/plain; charset=utf-8" });
    response.end(`${upstream.label} proxy failed: ${error.message}`);
  });

  request.pipe(proxyRequest);
});

server.listen(publicPort, host, () => {
  console.log(`LipiOCR frontend proxy listening on ${host}:${publicPort}`);
  console.log(`LipiOCR API proxy target ${internalApiUrl.origin}${internalApiUrl.pathname}`);
});

function shutdown() {
  server.close();
  next.kill("SIGTERM");
}

process.on("SIGTERM", shutdown);
process.on("SIGINT", shutdown);
