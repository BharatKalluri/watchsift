import { defineRailway, github, project, service } from "railway/iac";
export const partial = "backend";
export default defineRailway(() => {
  const backend = service("backend", {
    source: github("BharatKalluri/watchsift", {
      branch: "main",
      checkSuites: false,
      rootDirectory: "/backend",
    }),
    build: {
      buildEnvironment: "V3",
      builder: "DOCKERFILE",
      dockerfilePath: "Dockerfile",
      watchPatterns: ["/backend/**"],
    },
    healthcheck: "/health",
    replicas: { "asia-southeast1-eqsg3a": 1 },
    deploy: {
      limitOverride: { containers: { cpu: 0.5, memoryBytes: 500000000 } },
      restartPolicyMaxRetries: 3,
    },
  });

  return project("watchsift", {
    variables: { managed: false },
    resources: [backend],
  });
});
