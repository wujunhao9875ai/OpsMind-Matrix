import { defineStore } from "pinia";
import { ref } from "vue";
import type { Ticket, TicketLog, TicketStats, SlaStats } from "../types";
import { api } from "../api";

export const useTicketStore = defineStore("ticket", () => {
  const tickets = ref<Ticket[]>([]);
  const total = ref(0);
  const page = ref(1);
  const pageSize = ref(20);
  const loading = ref(false);
  const stats = ref<TicketStats | null>(null);
  const slaStats = ref<SlaStats | null>(null);

  const fetchTickets = async (params?: {
    status?: string;
    urgency?: string;
    page?: number;
  }) => {
    loading.value = true;
    try {
      const query = new URLSearchParams();
      if (params?.status) query.set("status", params.status);
      if (params?.urgency) query.set("urgency", params.urgency);
      query.set("page", String(params?.page || page.value));
      query.set("page_size", String(pageSize.value));

      const res = await api.get(`/dispatch/tickets?${query.toString()}`);
      tickets.value = res.data.items;
      total.value = res.data.total;
      page.value = res.data.page;
    } finally {
      loading.value = false;
    }
  };

  const fetchStats = async () => {
    const res = await api.get("/dispatch/stats");
    stats.value = res.data;
  };

  const fetchSlaStats = async () => {
    const res = await api.get("/dispatch/stats");
    slaStats.value = res.data;
  };

  const assignTicket = async (ticketId: string, engineerId?: string) => {
    await api.post("/dispatch/assign", { ticket_id: ticketId, engineer_id: engineerId });
  };

  const acceptTicket = async (ticketId: string) => {
    await api.post("/dispatch/accept", { ticket_id: ticketId });
  };

  const rejectTicket = async (ticketId: string, reason?: string) => {
    await api.post("/dispatch/reject", { ticket_id: ticketId, reason });
  };

  const resolveTicket = async (ticketId: string, resolution: string) => {
    await api.post("/dispatch/resolve", { ticket_id: ticketId, resolution });
  };

  return {
    tickets,
    total,
    page,
    pageSize,
    loading,
    stats,
    slaStats,
    fetchTickets,
    fetchStats,
    fetchSlaStats,
    assignTicket,
    acceptTicket,
    rejectTicket,
    resolveTicket,
  };
});