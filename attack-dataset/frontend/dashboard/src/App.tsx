import React, { useState, useCallback, Component, ErrorInfo, ReactNode, lazy, Suspense, useEffect } from "react";
import {
  Box, CssBaseline, ThemeProvider,
  AppBar, Toolbar, Typography, Drawer, List, ListItemButton,
  ListItemText, Divider, Chip, CircularProgress, Alert, Button,
  IconButton, useMediaQuery, useTheme,
} from "@mui/material";
import MenuIcon from "@mui/icons-material/Menu";
import SecurityIcon from "@mui/icons-material/Security";
import { useEngagement, useCommonShortcuts } from "./hooks";
import { darkTheme } from "./theme";
import { UserProfile as UserProfileType } from "./api";

// Direct imports for non-lazy components
import UserProfile from "./components/UserProfile";
import LoginModal from "./components/LoginModal";

// Lazy load panel components for code splitting
const EngagementPanel = lazy(() => import("./components/EngagementPanel"));
const SearchPanel = lazy(() => import("./components/SearchPanel"));
const AttackChainsPanel = lazy(() => import("./components/AttackChainsPanel"));
const OpsecPanel = lazy(() => import("./components/OpsecPanel"));
const OpSecAuditPanel = lazy(() => import("./components/OpSecAuditPanel"));
const AiChatPanel = lazy(() => import("./components/AiChatPanel"));
const SettingsPanel = lazy(() => import("./components/SettingsPanel"));
const EnhancedAutomationPanel = lazy(() => import("./components/EnhancedAutomationPanel"));
const ThreatEmulationPanel = lazy(() => import("./components/ThreatEmulationPanel"));
const HealthMonitorPanel = lazy(() => import("./components/HealthMonitorPanel"));
const MLPredictionPanel = lazy(() => import("./components/MLPredictionPanel"));
const PluginRunnerPanel = lazy(() => import("./components/PluginRunnerPanel"));
const MitreBrowserPanel = lazy(() => import("./components/MitreBrowserPanel"));
const OpSecQuickCheckPanel = lazy(() => import("./components/OpSecQuickCheckPanel"));

// ── Error Boundary ────────────────────────────────────────────────────────────
interface EBState { hasError: boolean; error?: Error; }
class ErrorBoundary extends Component<{ children: ReactNode; name: string }, EBState> {
  constructor(props: { children: ReactNode; name: string }) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError(error: Error): EBState { return { hasError: true, error }; }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`[ErrorBoundary:${this.props.name}]`, error, info);
  }
  render() {
    if (this.state.hasError) {
      return (
        <Alert severity="error" action={
          <Button size="small" onClick={() => this.setState({ hasError: false })}>Retry</Button>
        }>
          {this.props.name} panel crashed: {this.state.error?.message ?? "Unknown error"}
        </Alert>
      );
    }
    return this.props.children;
  }
}

// ── Loading Component ─────────────────────────────────────────────────────────
function PanelLoader() {
  return (
    <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", py: 8 }}>
      <CircularProgress sx={{ color: "#00e5ff" }} />
    </Box>
  );
}

const DRAWER_WIDTH = 220;

type Panel = "engagements" | "search" | "health" | "ml" | "plugins" | "mitre" | "opsec-quick" | "chains" | "opsec" | "audit" | "ai" | "automation" | "threat-emulation" | "settings";

// Panel display names for sidebar and title
const PANEL_NAMES: Record<Panel, string> = {
  engagements: "Engagements",
  search: "Search",
  health: "Health Monitor",
  ml: "ML Prediction",
  plugins: "Plugin Runner",
  mitre: "MITRE Browser",
  "opsec-quick": "OpSec Quick Check",
  chains: "Attack Chains",
  opsec: "OpSec Assessment",
  audit: "OpSec Chain Audit",
  ai: "AI Chat",
  automation: "Enhanced Automation",
  "threat-emulation": "Threat Emulation",
  settings: "Settings",
};

// Panel display order in sidebar
const PANEL_ORDER: Panel[] = [
  "engagements",
  "search",
  "health",
  "ml",
  "plugins",
  "mitre",
  "opsec-quick",
  "chains",
  "opsec",
  "audit",
  "ai",
  "automation",
  "threat-emulation",
  "settings",
];

export default function App() {
  const [panel, setPanel] = useState<Panel>("engagements");
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false);
  const [user, setUser] = useState<UserProfileType | null>(null);
  const [loginModalOpen, setLoginModalOpen] = useState(false);
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  // Use custom hook for engagement management
  const { engagements, active, setActive, refresh } = useEngagement();

  // Check for existing auth on mount
  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (token) {
      // User might be logged in - the actual validation happens in LoginModal
      // We just set a placeholder here to show the UI
      setUser(null); // Will be populated by LoginModal if token is valid
    }
  }, []);

  // Use custom hook for keyboard shortcuts
  useCommonShortcuts({
    onSearch: () => {
      setPanel("search");
      setMobileDrawerOpen(false);
      setTimeout(() => {
        const el = document.querySelector<HTMLInputElement>('[data-search-input]');
        el?.focus();
      }, 50);
    },
  });

  const statusColor = useCallback((s: string) => {
    if (s === "complete") return "success";
    if (s === "error")    return "error";
    if (s === "scanning" || s === "building_vectors") return "warning";
    return "default";
  }, []);

  return (
    <ThemeProvider theme={darkTheme}>
      <CssBaseline />
      <Box sx={{ display: "flex", minHeight: "100vh", bgcolor: "#0a0e1a" }}>
        {/* ── Sidebar ─────────────────────────────────────── */}
        <Drawer
          variant={isMobile ? "temporary" : "permanent"}
          open={isMobile ? mobileDrawerOpen : true}
          onClose={() => setMobileDrawerOpen(false)}
          sx={{
            width: DRAWER_WIDTH,
            "& .MuiDrawer-paper": {
              width: DRAWER_WIDTH,
              bgcolor: "linear-gradient(180deg, #0d1117 0%, #111827 100%)",
              borderRight: "1px solid #1f2937"
            },
          }}
          role="navigation"
          aria-label="Main navigation"
          ModalProps={{
            keepMounted: true, // Better mobile performance
          }}
        >
          <Toolbar sx={{ gap: 1, borderBottom: "1px solid #1f2937" }}>
            <SecurityIcon sx={{ color: "#00e5ff", fontSize: 28 }} aria-hidden="true" />
            <Typography variant="subtitle1" sx={{ color: "#00e5ff", fontWeight: 700, fontSize: "1.1rem" }}>
              OpsecAI
            </Typography>
          </Toolbar>
          <Divider />
          <nav aria-label="Primary navigation">
            <List dense role="menubar">
              {PANEL_ORDER.map((p) => (
                <ListItemButton
                  key={p}
                  selected={panel === p}
                  onClick={() => { setPanel(p); setMobileDrawerOpen(false); }}
                  role="menuitem"
                  aria-current={panel === p ? "page" : undefined}
                  sx={{
                    "&.Mui-selected": {
                      bgcolor: "linear-gradient(90deg, #00e5ff20 0%, transparent 100%)",
                      borderLeft: "3px solid #00e5ff"
                    },
                    borderLeft: "3px solid transparent",
                    borderRadius: "0 4px 4px 0",
                    mb: 0.5,
                    mx: 1
                  }}
                >
                  <ListItemText
                    primary={PANEL_NAMES[p]}
                    sx={{
                      "& .MuiTypography-root": {
                        color: panel === p ? "#00e5ff" : "#9ca3af",
                        fontWeight: panel === p ? 600 : 400,
                        fontSize: "0.875rem"
                      }
                    }}
                  />
                </ListItemButton>
              ))}
            </List>
          </nav>
          <Divider sx={{ borderColor: "#1f2937" }} />
          <Box sx={{ p: 1, overflowY: "auto", flex: 1 }} role="region" aria-label="Active engagements">
            <Typography variant="caption" sx={{ color: "#6b7280", pl: 1, fontWeight: 600, fontSize: "0.7rem" }}>
              ENGAGEMENTS
            </Typography>
            <List dense role="list">
              {engagements.map((e) => (
                <ListItemButton
                  key={e.id}
                  selected={active?.id === e.id}
                  onClick={() => { setActive(e); setPanel("engagements"); setMobileDrawerOpen(false); }}
                  role="listitem"
                  aria-label={`Engagement: ${e.target}, Status: ${e.status}`}
                  sx={{
                    py: 0.5,
                    "&.Mui-selected": {
                      bgcolor: "linear-gradient(90deg, #00e5ff20 0%, transparent 100%)",
                      borderLeft: "3px solid #00e5ff"
                    },
                    borderLeft: "3px solid transparent",
                    borderRadius: "0 4px 4px 0",
                    mx: 1,
                    mb: 0.5
                  }}
                >
                  <Box sx={{ overflow: "hidden" }}>
                    <Typography variant="caption" noWrap sx={{ display: "block", color: active?.id === e.id ? "#00e5ff" : "#9ca3af" }}>
                      {e.target}
                    </Typography>
                    <Chip
                      label={e.status}
                      size="small"
                      color={statusColor(e.status) as any}
                      sx={{ height: 16, fontSize: "0.6rem", mt: 0.5 }}
                    />
                  </Box>
                </ListItemButton>
              ))}
            </List>
          </Box>
        </Drawer>

        {/* ── Main ────────────────────────────────────────── */}
        <Box component="main" sx={{ flex: 1, display: "flex", flexDirection: "column", bgcolor: "#0a0e1a" }} role="main">
          <AppBar position="static" elevation={0}
            sx={{
              bgcolor: "linear-gradient(90deg, #0d1117 0%, #111827 100%)",
              borderBottom: "1px solid #1f2937"
            }}>
            <Toolbar variant="dense">
              {isMobile && (
                <IconButton
                  edge="start"
                  color="inherit"
                  aria-label="Open navigation menu"
                  onClick={() => setMobileDrawerOpen(true)}
                  sx={{ mr: 2 }}
                >
                  <MenuIcon />
                </IconButton>
              )}
              <Typography variant="h6" sx={{ color: "#00e5ff", flex: 1 }} id="page-title">
                {panel === "engagements" && (active ? `Engagement: ${active.target}` : PANEL_NAMES[panel])}
                {panel !== "engagements" && PANEL_NAMES[panel]}
              </Typography>
              {active && panel === "engagements" && (
                <Chip
                  label={active.status}
                  color={statusColor(active.status) as any}
                  size="small"
                  icon={active.status === "scanning" || active.status === "building_vectors"
                    ? <CircularProgress size={12} color="inherit" aria-label="Loading" /> : undefined}
                  aria-label={`Status: ${active.status}`}
                  sx={{ mr: 2 }}
                />
              )}
              <UserProfile
                user={user}
                onLogin={() => setLoginModalOpen(true)}
                onLogout={() => setUser(null)}
              />
            </Toolbar>
          </AppBar>

          <Box sx={{
            flex: 1,
            overflow: "auto",
            p: 2,
            backgroundImage: "radial-gradient(circle at top right, #1e3a5f10 0%, transparent 50%)"
          }}
          role="region"
          aria-labelledby="page-title"
          >
            <Suspense fallback={<PanelLoader />}>
              {panel === "engagements" &&
                <ErrorBoundary name="Engagements">
                  <EngagementPanel active={active} onNew={(e) => { setActive(e); refresh(); }} />
                </ErrorBoundary>}
              {panel === "search" &&
                <ErrorBoundary name="Search">
                  <SearchPanel />
                </ErrorBoundary>}
              {panel === "health" &&
                <ErrorBoundary name="Health Monitor">
                  <HealthMonitorPanel />
                </ErrorBoundary>}
              {panel === "ml" &&
                <ErrorBoundary name="ML Prediction">
                  <MLPredictionPanel />
                </ErrorBoundary>}
              {panel === "plugins" &&
                <ErrorBoundary name="Plugin Runner">
                  <PluginRunnerPanel />
                </ErrorBoundary>}
              {panel === "mitre" &&
                <ErrorBoundary name="MITRE Browser">
                  <MitreBrowserPanel />
                </ErrorBoundary>}
              {panel === "opsec-quick" &&
                <ErrorBoundary name="OpSec Quick Check">
                  <OpSecQuickCheckPanel />
                </ErrorBoundary>}
              {panel === "chains" &&
                <ErrorBoundary name="Attack Chains">
                  <AttackChainsPanel engagement={active} />
                </ErrorBoundary>}
              {panel === "opsec" &&
                <ErrorBoundary name="OpSec">
                  <OpsecPanel engagement={active} />
                </ErrorBoundary>}
              {panel === "audit" &&
                <ErrorBoundary name="OpSec Audit">
                  <OpSecAuditPanel engagementId={active?.id || null} chains={active?.attack_chains?.chains || []} />
                </ErrorBoundary>}
              {panel === "ai" &&
                <ErrorBoundary name="AI Chat">
                  <AiChatPanel engagement={active} />
                </ErrorBoundary>}
              {panel === "automation" &&
                <ErrorBoundary name="Enhanced Automation">
                  <EnhancedAutomationPanel />
                </ErrorBoundary>}
              {panel === "threat-emulation" &&
                <ErrorBoundary name="Threat Emulation">
                  <ThreatEmulationPanel />
                </ErrorBoundary>}
              {panel === "settings" &&
                <ErrorBoundary name="Settings">
                  <SettingsPanel />
                </ErrorBoundary>}
            </Suspense>
          </Box>
        </Box>
      </Box>

      {/* Login Modal */}
      <LoginModal
        open={loginModalOpen}
        onClose={() => setLoginModalOpen(false)}
        onLogin={(user) => setUser(user)}
      />
    </ThemeProvider>
  );
}
