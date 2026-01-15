export default defineNuxtConfig({
  compatibilityDate: "2026-01-14",
  ssr: true,
  modules: ["@nuxtjs/tailwindcss"],
  app: {
    head: {
      title: "Nelson Fabian Rey - Solutions Architect & Full Stack Developer",
      meta: [
        {
          name: "description",
          content:
            "Nelson Fabian Rey - Solutions Architect & Senior Full Stack Developer specializing in Kubernetes, cloud-native architectures, and production-grade systems",
        },
        { name: "author", content: "Nelson Fabian Rey" },
      ],
    },
  },
});
