<template>
  <div class="main-layout">
    <el-container>
      <el-header class="top-nav">
        <div class="nav-left">
          <span class="logo">运维 AI 平台</span>
          <el-menu
            :default-active="activeMenu"
            mode="horizontal"
            router
            class="nav-menu"
          >
            <el-menu-item index="/chat">
              <el-icon><ChatDotRound /></el-icon>
              <span>AI 聊天</span>
            </el-menu-item>
            <el-menu-item v-if="role === 'engineer'" index="/engineer">
              <el-icon><Tools /></el-icon>
              <span>工程师工作台</span>
            </el-menu-item>
            <el-menu-item v-if="role === 'storekeeper'" index="/storekeeper">
              <el-icon><Box /></el-icon>
              <span>库房管理</span>
            </el-menu-item>
            <el-menu-item v-if="role === 'admin'" index="/admin">
              <el-icon><DataBoard /></el-icon>
              <span>管理后台</span>
            </el-menu-item>
          </el-menu>
        </div>
        <div class="nav-right">
          <span class="user-info">
            <el-tag :type="roleTagType" size="small">{{ roleLabel }}</el-tag>
            {{ username }}
          </span>
          <el-button type="danger" size="small" @click="logout">退出登录</el-button>
        </div>
      </el-header>
      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter, useRoute } from "vue-router";
import { ChatDotRound, Tools, Box, DataBoard } from "@element-plus/icons-vue";

const router = useRouter();
const route = useRoute();

const username = ref(localStorage.getItem("username") || "");
const role = ref(localStorage.getItem("role") || "user");

const activeMenu = computed(() => {
  if (route.path.startsWith("/engineer")) return "/engineer";
  if (route.path.startsWith("/storekeeper")) return "/storekeeper";
  if (route.path.startsWith("/admin")) return "/admin";
  return "/chat";
});

const roleLabel = computed(() => {
  const map: Record<string, string> = { admin: "管理员", engineer: "工程师", storekeeper: "库管员", user: "用户" };
  return map[role.value] || "用户";
});

const roleTagType = computed(() => {
  const map: Record<string, string> = { admin: "danger", engineer: "warning", storekeeper: "success", user: "info" };
  return map[role.value] || "info";
});

function logout() {
  localStorage.removeItem("token");
  localStorage.removeItem("username");
  localStorage.removeItem("role");
  router.push("/login");
}
</script>

<style scoped>
.main-layout { height: 100vh; display: flex; flex-direction: column; }
.top-nav { display: flex; justify-content: space-between; align-items: center; background: #fff; border-bottom: 1px solid #e4e7ed; padding: 0 20px; height: 60px; }
.nav-left { display: flex; align-items: center; gap: 20px; }
.logo { font-size: 18px; font-weight: bold; color: #409eff; white-space: nowrap; }
.nav-menu { border-bottom: none !important; }
.nav-menu .el-menu-item { height: 60px; line-height: 60px; }
.nav-right { display: flex; align-items: center; gap: 12px; }
.user-info { font-size: 14px; color: #606266; }
.main-content { flex: 1; padding: 0; background: #f5f7fa; overflow: auto; }
</style>