import React, { useState, useEffect } from "react";
import {
  Box, Button, TextField, Typography, Paper, Chip,
  Table, TableBody, TableCell, TableHead, TableRow, Alert,
} from "@mui/material";
import { Engagement, startEngagement, subscribeEngagement } from "../api";

interface Props {
  active: Engagement | null;
  onNew: (e: Engagement) => void;
}

export default function EngagementPanel({ active, onNew }: Props) {
  const [target, setTarget]   = useState("");
  const [loading, setLoading] = useState(false);
  const [live, setLive]       = useState<Engagement | null>(active);

  useEffect(() => { setLive(active); }, [active]);

  const activeId = active?.id;
  useEffect(() => {
    if (!activeId) return;
    const unsub = subscribeEngagement(activeId, setLive);
    return unsub;
  }, [activeId]);

  const handleStart = async () => {
    if (!target.trim()) return;
    setLoading(true);
    try {
      const { engagement_id } = await startEngagement(target.trim());
      // poll once to get initial state
      const resp = await fetch(
        `${process.env.REACT_APP_ORCHESTRATOR_URL || "http://localhost:3001"}/engagements/${engagement_id}`
      );
      const eng: Engagement = await resp.json();
      onNew(eng);
      setTarget("");
    } finally {
      setLoading(false);
    }
  };

  const eng = live;

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {/* ── Start new engagement ── */}
      <Paper sx={{ p: 2, bgcolor: "#111827" }}>
        <Typography variant="subtitle2" sx={{ mb: 1, color: "#00e5ff" }}>
          New Engagement
        </Typography>
        <Box sx={{ display: "flex", gap: 1 }}>
          <TextField
            size="small" fullWidth
            placeholder="Target IP / hostname (e.g. 192.168.1.10)"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleStart()}
            sx={{ "& .MuiOutlinedInput-root": { fontFamily: "monospace" } }}
          />
          <Button variant="contained" onClick={handleStart} disabled={loading}>
            {loading ? "Starting…" : "Engage"}
          </Button>
        </Box>
      </Paper>

      {eng && (
        <>
          {/* ── Status ── */}
          <Paper sx={{ p: 2, bgcolor: "#111827" }}>
            <Box sx={{ display: "flex", gap: 1, alignItems: "center", mb: 1 }}>
              <Typography variant="subtitle2" sx={{ color: "#00e5ff" }}>
                Target: {eng.target}
              </Typography>
              <Chip label={eng.status} size="small"
                color={eng.status === "complete" ? "success" : eng.status === "error" ? "error" : "warning"} />
            </Box>

            {/* Log */}
            <Box sx={{
              bgcolor: "#0a0e1a", borderRadius: 1, p: 1,
              maxHeight: 140, overflowY: "auto", fontFamily: "monospace", fontSize: "0.72rem",
            }}>
              {(eng.log || []).map((l, i) => (
                <Box key={i} sx={{ color: "#6b7280" }}>
                  <span style={{ color: "#374151" }}>[{new Date(l.ts).toLocaleTimeString()}]</span>{" "}
                  <span style={{ color: "#d1d5db" }}>{l.msg}</span>
                </Box>
              ))}
            </Box>
          </Paper>

          {/* ── Fingerprint ── */}
          {eng.scan_session?.fingerprint && (
            <Paper sx={{ p: 2, bgcolor: "#111827" }}>
              <Typography variant="subtitle2" sx={{ color: "#00e5ff", mb: 1 }}>
                Target Fingerprint
              </Typography>
              <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap", mb: 1 }}>
                <Chip label={`IP: ${eng.scan_session.fingerprint.ip}`} size="small" />
                {eng.scan_session.fingerprint.os && (
                  <Chip label={`OS: ${eng.scan_session.fingerprint.os}`} size="small" color="info" />
                )}
              </Box>
              {eng.scan_session.fingerprint.services?.length > 0 && (
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ color: "#6b7280" }}>Port</TableCell>
                      <TableCell sx={{ color: "#6b7280" }}>Service</TableCell>
                      <TableCell sx={{ color: "#6b7280" }}>Product</TableCell>
                      <TableCell sx={{ color: "#6b7280" }}>Version</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {eng.scan_session.fingerprint.services.map((s, i) => (
                      <TableRow key={i}>
                        <TableCell sx={{ fontFamily: "monospace" }}>{s.port}/{s.protocol}</TableCell>
                        <TableCell>{s.name}</TableCell>
                        <TableCell>{s.product}</TableCell>
                        <TableCell>{s.version}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </Paper>
          )}

          {/* ── OpSec summary ── */}
          {eng.opsec_reports && (
            <Alert
              severity={eng.opsec_reports.risk_score >= 70 ? "error"
                : eng.opsec_reports.risk_score >= 40 ? "warning" : "success"}
            >
              <strong>OpSec Risk Score: {eng.opsec_reports.risk_score}/100</strong> —{" "}
              {eng.opsec_reports.total_findings} findings.{" "}
              {eng.opsec_reports.global_findings?.[0]?.title || ""}
            </Alert>
          )}
        </>
      )}

      {!eng && (
        <Paper sx={{ p: 4, bgcolor: "#111827", textAlign: "center" }}>
          <Typography sx={{ color: "#6b7280" }}>
            Start an engagement or select one from the sidebar.
          </Typography>
        </Paper>
      )}
    </Box>
  );
}
