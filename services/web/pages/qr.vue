<script setup lang="ts">
import QRCode from "qrcode";

useHead({
  title: "Espacio Raíz Consciente - Telegram",
  meta: [
    {
      name: "description",
      content: "Únete a Espacio Raíz Consciente en Telegram",
    },
  ],
});

const telegramUrl = "https://t.me/espacioraizconsciente";
const qrDataUrl = ref<string>("");

onMounted(async () => {
  qrDataUrl.value = await QRCode.toDataURL(telegramUrl, {
    width: 400,
    margin: 2,
    color: {
      dark: "#1a3a2f",
      light: "#f8f5f0",
    },
    errorCorrectionLevel: "H",
  });
});
</script>

<template>
  <div
    class="relative min-h-screen overflow-hidden bg-gradient-to-br from-stone-100 via-amber-50 to-emerald-50"
  >
    <!-- Decorative background elements -->
    <div class="absolute inset-0 overflow-hidden">
      <div
        class="absolute -left-32 -top-32 h-96 w-96 rounded-full bg-emerald-200/30 blur-3xl"
      />
      <div
        class="absolute -bottom-32 -right-32 h-[500px] w-[500px] rounded-full bg-amber-200/40 blur-3xl"
      />
      <div
        class="absolute left-1/2 top-1/3 h-64 w-64 -translate-x-1/2 rounded-full bg-teal-100/30 blur-2xl"
      />
      <!-- Subtle pattern overlay -->
      <div
        class="absolute inset-0 opacity-[0.015]"
        style="
          background-image: url('data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2260%22 height=%2260%22><circle cx=%2230%22 cy=%2230%22 r=%221%22 fill=%22%23000%22/></svg>');
        "
      />
    </div>

    <div class="relative flex min-h-screen flex-col items-center justify-center px-6 py-12">
      <!-- Main card -->
      <div
        class="w-full max-w-md rounded-3xl border border-emerald-900/5 bg-white/70 p-10 shadow-2xl shadow-emerald-900/10 backdrop-blur-xl"
      >
        <!-- Logo/Title area -->
        <div class="mb-8 text-center">
          <div
            class="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-600 to-teal-700 shadow-lg shadow-emerald-600/30"
          >
            <svg
              class="h-8 w-8 text-white"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="1.5"
                d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"
              />
            </svg>
          </div>
          <h1
            class="font-serif text-3xl font-light tracking-wide text-emerald-900"
            style="font-family: 'Cormorant Garamond', Georgia, serif"
          >
            Espacio Raíz
          </h1>
          <p class="mt-1 text-lg font-light tracking-widest text-emerald-700/80">
            CONSCIENTE
          </p>
        </div>

        <!-- QR Code -->
        <div class="flex justify-center">
          <div
            class="rounded-2xl bg-gradient-to-br from-stone-50 to-amber-50/50 p-4 shadow-inner"
          >
            <img
              v-if="qrDataUrl"
              :src="qrDataUrl"
              alt="QR Code para Telegram"
              class="h-64 w-64 rounded-xl"
            />
            <div
              v-else
              class="flex h-64 w-64 items-center justify-center rounded-xl bg-stone-100"
            >
              <div class="h-8 w-8 animate-spin rounded-full border-2 border-emerald-600 border-t-transparent" />
            </div>
          </div>
        </div>

        <!-- Instructions -->
        <div class="mt-8 text-center">
          <p class="text-sm font-medium text-emerald-800">
            Escanea el código QR
          </p>
          <p class="mt-1 text-xs text-stone-500">
            para unirte a nuestro canal de Telegram
          </p>
        </div>

        <!-- Divider -->
        <div class="my-6 flex items-center gap-4">
          <div class="h-px flex-1 bg-gradient-to-r from-transparent via-emerald-200 to-transparent" />
          <span class="text-xs font-light tracking-widest text-stone-400">O</span>
          <div class="h-px flex-1 bg-gradient-to-r from-transparent via-emerald-200 to-transparent" />
        </div>

        <!-- Direct link button -->
        <a
          :href="telegramUrl"
          target="_blank"
          rel="noopener noreferrer"
          class="flex w-full items-center justify-center gap-3 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 px-6 py-4 text-white shadow-lg shadow-emerald-600/25 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-xl hover:shadow-emerald-600/30"
        >
          <!-- Telegram icon -->
          <svg class="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
            <path
              d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"
            />
          </svg>
          <span class="text-sm font-medium">Abrir en Telegram</span>
        </a>
      </div>

      <!-- Footer -->
      <p class="mt-8 text-center text-xs text-stone-400">
        Un espacio para el crecimiento y la consciencia
      </p>
    </div>
  </div>
</template>

<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500&display=swap');
</style>
