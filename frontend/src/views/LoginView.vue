<template>
  <div class="login-container">
    <el-card class="login-card">
      <h2>运维 AI 平台</h2>
      <el-form :model="form" label-width="80px">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" placeholder="请输入密码" @keyup.enter="login" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="login" :loading="loading">登录</el-button>
        </el-form-item>
      </el-form>
      <p class="hint">测试账号: admin / Admin@2024Demo</p>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { authAPI } from "../api";

const router = useRouter();
const loading = ref(false);
const form = reactive({ username: "", password: "" });

async function login() {
  loading.value = true;
  try {
    const { data } = await authAPI.login(form.username, form.password);
    localStorage.setItem("token", data.access_token);
    localStorage.setItem("username", data.username || form.username);
    localStorage.setItem("role", data.role || "user");
    if (data.role === "admin") {
      router.push("/admin");
    } else if (data.role === "engineer") {
      router.push("/engineer");
    } else if (data.role === "storekeeper") {
      router.push("/storekeeper");
    } else {
      router.push("/chat");
    }
  } catch {
    ElMessage.error("用户名或密码错误");
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background: #f0f2f5;
}
.login-card {
  width: 400px;
}
.login-card h2 {
  text-align: center;
  margin-bottom: 20px;
}
.hint {
  text-align: center;
  color: #999;
  font-size: 12px;
}
</style>