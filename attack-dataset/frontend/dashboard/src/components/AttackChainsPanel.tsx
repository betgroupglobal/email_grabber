import React, { useState } from "react";
import {
  Box, Paper, Typography, Chip, Stepper, Step,
  StepLabel, StepContent, Button,
} from "@mui/material";
import { Engagement, AttackChain } from "../api";

interface Props { engagement: Engagement | null; }

const PHASE_COLORS: Record<string, string> = {
  Reconnaissance: "#6366f1",
  "Initial Access": "#ef4444",
  Execution: "#f97316",
  Persistence: "#eab308",
  "Privilege Escalation": "#ec4899",
  "Defense Evasion": "#8b5cf6",
  "Credential Access": "#06b6d4",
  "Lateral Movement": "#10b981",
  Exfiltration: "#f43f5e",
  Impact: "#dc2626",
};

function ChainView({ chain }: { chain: AttackChain }) {
  const [active, setActive] = useState(0);

  return (
    <Paper sx={{ p: 2, bgcolor: "#0d1117", mb: 2 }}>
      <Box sx={{ display: "flex", gap: 1, alignItems: "center", mb: 2 }}>
        <Typography variant="subtitle2" sx={{ color: "#00e5ff" }}>
          Chain {chain.chain_id}
        </Typography>
        <Chip
          label={`${(chain.confidence * 100).toFixed(0)}% confidence`}
          size="small"
          color={chain.confidence >= 0.6 ? "error" : "warning"}
        />
        <Chip label={`${chain.steps.length} steps`} size="small" variant="outlined" />
      </Box>

      <Stepper activeStep={active} orientation="vertical" nonLinear>
        {chain.steps.map((step, i) => (
          <Step key={i} completed={false}>
            <StepLabel
              onClick={() => setActive(i)}
              sx={{ cursor: "pointer", "& .MuiStepIcon-root": { color: PHASE_COLORS[step.phase] || "#6b7280" } }}
            >
              <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
                <span>{step.phase}</span>
                <Chip label={step.attack.attack_type} size="small" variant="outlined" sx={{ fontSize: "0.65rem" }} />
              </Box>
            </StepLabel>
            <StepContent>
              <Box sx={{ display: "flex", flexDirection: "column", gap: 1, mb: 1 }}>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>{step.attack.title}</Typography>
                {step.attack.mitre_technique && (
                  <Chip label={step.attack.mitre_technique.split(",")[0].trim()} size="small" color="info" sx={{ alignSelf: "flex-start" }} />
                )}
                <Box>
                  <Typography variant="caption" sx={{ color: "#6b7280" }}>TOOLS</Typography>
                  <Typography variant="body2" sx={{ fontFamily: "monospace", fontSize: "0.72rem" }}>
                    {step.attack.tools_used}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="caption" sx={{ color: "#6b7280" }}>IMPACT</Typography>
                  <Typography variant="body2">{step.attack.impact}</Typography>
                </Box>
              </Box>
              <Box sx={{ display: "flex", gap: 1 }}>
                <Button size="small" disabled={i === 0} onClick={() => setActive(i - 1)}>Back</Button>
                <Button size="small" variant="contained" disabled={i === chain.steps.length - 1}
                  onClick={() => setActive(i + 1)}>Next</Button>
              </Box>
            </StepContent>
          </Step>
        ))}
      </Stepper>

      {/* OpSec notes */}
      <Box sx={{ mt: 2, p: 1, bgcolor: "#1a1a2e", borderRadius: 1, borderLeft: "3px solid #f59e0b" }}>
        <Typography variant="caption" sx={{ color: "#f59e0b" }}>OPSEC NOTES</Typography>
        <Typography variant="body2" sx={{ fontSize: "0.72rem", mt: 0.5 }}>
          {chain.opsec_notes}
        </Typography>
      </Box>

      {/* Impact */}
      <Box sx={{ mt: 1, p: 1, bgcolor: "#1a0a0a", borderRadius: 1, borderLeft: "3px solid #ef4444" }}>
        <Typography variant="caption" sx={{ color: "#ef4444" }}>ESTIMATED IMPACT</Typography>
        <Typography variant="body2" sx={{ fontSize: "0.72rem", mt: 0.5 }}>
          {chain.estimated_impact}
        </Typography>
      </Box>
    </Paper>
  );
}

export default function AttackChainsPanel({ engagement }: Props) {
  const chains = engagement?.attack_chains?.chains || [];

  if (!engagement) {
    return (
      <Paper sx={{ p: 4, bgcolor: "#111827", textAlign: "center" }}>
        <Typography sx={{ color: "#6b7280" }}>Select an engagement to view attack chains.</Typography>
      </Paper>
    );
  }

  if (chains.length === 0) {
    return (
      <Paper sx={{ p: 4, bgcolor: "#111827", textAlign: "center" }}>
        <Typography sx={{ color: "#6b7280" }}>
          {engagement.status === "complete"
            ? "No attack chains generated for this target."
            : `Status: ${engagement.status} — chains will appear when ready.`}
        </Typography>
      </Paper>
    );
  }

  return (
    <Box>
      <Typography variant="subtitle2" sx={{ color: "#00e5ff", mb: 2 }}>
        {chains.length} Attack Chain{chains.length !== 1 ? "s" : ""} — Target: {engagement.target}
      </Typography>
      {chains.map((c) => <ChainView key={c.chain_id} chain={c} />)}
    </Box>
  );
}
