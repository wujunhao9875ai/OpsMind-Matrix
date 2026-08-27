import { ref, onUnmounted } from "vue";

export function useStorekeeperWebSocket() {
  const messages = ref<Array<{ role: string; content: string }>>([]);
  const connected = ref(false);
  let ws: WebSocket | null = null;

  function connect() {
    const token = localStorage.getItem("token");
    if (!token) return;

    const sessionId = crypto.randomUUID();
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${location.host}/ws/storekeeper/chat/${sessionId}?token=${token}`;

    ws = new WebSocket(url);

    ws.onopen = () => { connected.value = true; };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "message") {
          messages.value.push(data.payload);
        }
      } catch (e) {
        console.error("WebSocket message parse error:", e);
      }
    };

    ws.onclose = () => { connected.value = false; };
    ws.onerror = () => { connected.value = false; };
  }

  function sendMessage(content: string) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    messages.value.push({ role: "user", content });
    ws.send(JSON.stringify({ type: "message", payload: { content } }));
  }

  function disconnect() {
    if (ws) { ws.close(); ws = null; }
  }

  onUnmounted(() => { disconnect(); });

  return { messages, connected, connect, sendMessage, disconnect };
}