import React, { useState, useEffect, useCallback } from "react";
import {
  Box, CssBaseline, ThemeProvider, createTheme,
  AppBar, Toolbar, Typography, Drawer, List, ListItemButton,
  ListItemText, Divider, Chip, CircularProgress,
} from "@mui/material";
import SecurityIcon from "@mui/icons-material/Security";
import EngagementPanel from "./components/EngagementPanel";
import SearchPanel from "./components/SearchPanel";
import AttackChainsPanel from "./components/AttackChainsPanel";
import OpsecPanel from "./components/OpsecPanel";
import { Engagement, listEngagements } from "./api";

const DRAWER_WIDTH = 220;

const darkTheme = createTheme({
  palette: {
    mode: "dark",
    primary:   { main: "#00e5ff" },
    secondary: { main: "#ff4444" },
    background: { default: "#0a0e1a", paper: "#111827" },
  },
  typography: { fontFamily: "monospace, 'Courier New'" },
});

type Panel = "engagements" | "search" | "chains" | "opsec";

export default function App() {
  const [panel, setPanel]       = useState<Panel>("engagements");
  const [engagements, setEngagements] = useState<Engagement[]>([]);
  const [active, setActive]     = useState<Engagement | null>(null);

  const refresh = useCallback(async () => {
    try {
      const list = await listEngagements();
      setEngagements(list);
      if (active) {
        const updated = list.find((e) => e.id === active.id);
        if (updated) setActive(updated);
      }
    } catch { /* backend might not be up yet */ }
  }, [active]);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 4000);
    return () => clearInterval(t);
  }, [refresh]);

  const statusColor = (s: string) => {
    if (s === "complete") return "success";
    if (s === "error")    return "error";
    if (s === "scanning" || s === "building_vectors") return "warning";
    return "default";
  };

  return (
    <ThemeProvider theme={darkTheme}>
      <CssBaseline />
      <Box sx={{ display: "flex", minHeight: "100vh" }}>
        {/* ── Sidebar ─────────────────────────────────────── */}
        <Drawer variant="permanent" sx={{
          width: DRAWER_WIDTH,
          "& .MuiDrawer-paper": { width: DRAWER_WIDTH, bgcolor: "#0d1117", borderRight: "1px solid #1f2937" },
        }}>
          <Toolbar sx={{ gap: 1 }}>
            <SecurityIcon sx={{ color: "#00e5ff" }} />
            <Typography variant="subtitle1" sx={{ color: "#00e5ff", fontWeight: 700 }}>
              OpsecAI
            </Typography>
          </Toolbar>
          <Divider />
          <List dense>
            {(["engagements", "search", "chains", "opsec"] as Panel[]).map((p) => (
              <ListItemButton
                key={p}
                selected={panel === p}
                onClick={() => setPanel(p)}
                sx={{ "&.Mui-selected": { bgcolor: "#1f2937" } }}
              >
                <ListItemText primary={p.charAt(0).toUpperCase() + p.slice(1)} />
              </ListItemButton>
            ))}
          </List>
          <Divider />
          <Box sx={{ p: 1, overflowY: "auto", flex: 1 }}>
            <Typography variant="caption" sx={{ color: "#6b7280", pl: 1 }}>
              ENGAGEMENTS
            </Typography>
            {engagements.map((e) => (
              <ListItemButton
                key={e.id}
                selected={active?.id === e.id}
                onClick={() => { setActive(e); setPanel("engagements"); }}
                sx={{ py: 0.5, "&.Mui-selected": { bgcolor: "#1f2937" } }}
              >
                <Box sx={{ overflow: "hidden" }}>
                  <Typography variant="caption" noWrap sx={{ display: "block" }}>
                    {e.target}
                  </Typography>
                  <Chip
                    label={e.status}
                    size="small"
                    color={statusColor(e.status) as any}
                    sx={{ height: 16, fontSize: "0.6rem" }}
                  />
                </Box>
              </ListItemButton>
            ))}
          </Box>
        </Drawer>

        {/* ── Main ────────────────────────────────────────── */}
        <Box component="main" sx={{ flex: 1, display: "flex", flexDirection: "column" }}>
          <AppBar position="static" elevation={0}
            sx={{ bgcolor: "#0d1117", borderBottom: "1px solid #1f2937" }}>
            <Toolbar variant="dense">
              <Typography variant="h6" sx={{ color: "#00e5ff", flex: 1 }}>
                {panel === "engagements" && (active ? `Engagement: ${active.target}` : "Engagements")}
                {panel === "search"      && "Attack Knowledge Search"}
                {panel === "chains"      && "Attack Chains"}
                {panel === "opsec"       && "OpSec Assessment"}
              </Typography>
              {active && (
                <Chip
                  label={active.status}
                  color={statusColor(active.status) as any}
                  size="small"
                  icon={active.status === "scanning" || active.status === "building_vectors"
                    ? <CircularProgress size={12} color="inherit" /> : undefined}
                />
              )}
            </Toolbar>
          </AppBar>

          <Box sx={{ flex: 1, overflow: "auto", p: 2 }}>
            {panel === "engagements" &&
              <EngagementPanel active={active} onNew={(e) => { setActive(e); refresh(); }} />}
            {panel === "search"  && <SearchPanel />}
            {panel === "chains"  && <AttackChainsPanel engagement={active} />}
            {panel === "opsec"   && <OpsecPanel engagement={active} />}
          </Box>
        </Box>
      </Box>
    </ThemeProvider>
  );
}
