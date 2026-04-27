// ============================================================
//  悠米 AI 对话空间 - Vue 3 应用逻辑
//  WebSocket 流式对话、双主题切换、消息管理
// ============================================================

const { createApp, ref, nextTick, watch, onMounted, onBeforeUnmount } = Vue;

const app = createApp({
  setup() {
    // ---------------------------- 响应式状态 ----------------------------
    const theme = ref(localStorage.getItem('yumi-theme') || 'light');
    const messages = ref([]);               // 历史消息列表 { role, content, text, streaming }
    const userMessage = ref('');            // 输入框内容
    const streaming = ref(false);           // 是否正在接收流式回复
    const streamContent = ref('');          // 当前流式内容（HTML）
    const streamText = ref('');             // 当前流式纯文本（用于复制）
    const connectionStatus = ref('disconnected'); // 'connecting' | 'connected' | 'disconnected'

    let ws = null;
    let reconnectTimer = null;
    const chatContainer = ref(null);
    const userInput = ref(null);

    // ---------------------------- 主题切换 ----------------------------
    function toggleTheme() {
      theme.value = theme.value === 'light' ? 'dark' : 'light';
      localStorage.setItem('yumi-theme', theme.value);
      nextTick(() => {
        lucide.createIcons();
      });
    }

    // ---------------------------- WebSocket 连接 ----------------------------
    function connectWebSocket() {
      if (ws && ws.readyState === WebSocket.OPEN) return;

      connectionStatus.value = 'connecting';
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/ws/chat`;

      try {
        ws = new WebSocket(wsUrl);
      } catch (e) {
        connectionStatus.value = 'disconnected';
        scheduleReconnect();
        return;
      }

      ws.onopen = () => {
        connectionStatus.value = 'connected';
        console.log('悠米 WebSocket 已连接');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          // 错误处理
          if (data.error) {
            console.error('悠米回复错误:', data.error);
            if (streaming.value) {
              // 显示错误在流中
              streamContent.value += `<span class="error-msg">⚠️ ${escapeHtml(data.error)}</span>`;
              finishStreaming();
            }
            return;
          }
          // 流式 token
          if (data.token) {
            if (!streaming.value) {
              // 开始流式
              streaming.value = true;
              streamContent.value = '';
              streamText.value = '';
              scrollToBottom();
            }
            streamText.value += data.token;
            streamContent.value += escapeHtml(data.token);
            scrollToBottom();
          }
          // 结束标记
          if (data.done) {
            finishStreaming();
          }
        } catch (e) {
          console.error('消息解析错误:', e);
        }
      };

      ws.onclose = () => {
        connectionStatus.value = 'disconnected';
        console.log('悠米 WebSocket 断开');
        // 非正常关闭时尝试重连
        if (!streaming.value) {
          scheduleReconnect();
        }
      };

      ws.onerror = (err) => {
        console.error('WebSocket 错误:', err);
        connectionStatus.value = 'disconnected';
      };
    }

    function scheduleReconnect() {
      if (reconnectTimer) return;
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        if (connectionStatus.value !== 'connected') {
          console.log('尝试重新连接悠米...');
          connectWebSocket();
        }
      }, 3000);
    }

    function finishStreaming() {
      if (streaming.value) {
        // 将流式消息保存到历史
        messages.value.push({
          role: 'assistant',
          content: streamContent.value,
          text: streamText.value,
          streaming: false,
        });
        streamContent.value = '';
        streamText.value = '';
        streaming.value = false;
        scrollToBottom();
        nextTick(() => {
          lucide.createIcons();
        });
      }
    }

    // ---------------------------- 发送消息 ----------------------------
    function sendMessage() {
      const text = userMessage.value.trim();
      if (!text || streaming.value) return;
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        alert('未连接到悠米服务，请稍后重试');
        connectWebSocket();
        return;
      }

      // 添加用户消息
      messages.value.push({
        role: 'user',
        content: escapeHtml(text),
        text: text,
        streaming: false,
      });
      userMessage.value = '';
      scrollToBottom();

      // 发送到后端
      ws.send(JSON.stringify({ content: text }));
      nextTick(() => {
        userInput.value?.focus();
      });
    }

    // 处理回车发送/换行
    function newline(e) {
      // Shift+Enter 换行由 textarea 默认行为处理，无需额外操作
    }

    // ---------------------------- 清空对话 ----------------------------
    function clearChat() {
      if (streaming.value) {
        // 如果正在流式，结束并保存后再清空
        finishStreaming();
      }
      messages.value = [];
      streamContent.value = '';
      streamText.value = '';
      scrollToBottom();
    }

    // ---------------------------- 复制文本 ----------------------------
    function copyText(text) {
      navigator.clipboard.writeText(text).then(() => {
        // 可选提示（轻量）
      }).catch(err => {
        console.error('复制失败:', err);
      });
    }

    // ---------------------------- 工具函数 ----------------------------
    function escapeHtml(text) {
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    }

    function scrollToBottom() {
      nextTick(() => {
        if (chatContainer.value) {
          chatContainer.value.scrollTop = chatContainer.value.scrollHeight;
        }
      });
    }

    // ---------------------------- 生命周期 ----------------------------
    onMounted(() => {
      connectWebSocket();
      nextTick(() => {
        lucide.createIcons();
        feather.replace();
      });
    });

    onBeforeUnmount(() => {
      if (ws) {
        ws.close();
        ws = null;
      }
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
      }
    });

    // 监听主题变化，更新图标颜色（需要时重新渲染）
    watch(theme, () => {
      nextTick(() => {
        lucide.createIcons();
        feather.replace();
      });
    });

    // ---------------------------- 返回给模板 ----------------------------
    return {
      theme,
      messages,
      userMessage,
      streaming,
      streamContent,
      connectionStatus,
      chatContainer,
      userInput,
      toggleTheme,
      sendMessage,
      newline,
      clearChat,
      copyText,
    };
  },
});

app.mount('#app');