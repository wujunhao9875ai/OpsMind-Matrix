<template>
  <router-view v-if="isLoginPage" />
  <router-view v-else-if="isChatPage" />
  <MainLayout v-else />
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import MainLayout from "./components/MainLayout.vue";

const route = useRoute();
const isLoginPage = computed(() => route.path === "/login");
const isChatPage = computed(() => route.path === "/chat" || route.path === "/");
</script>

<style>
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
}
</style>