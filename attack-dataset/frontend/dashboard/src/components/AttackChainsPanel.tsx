import React from "react";
import { Box, Paper, Typography } from "@mui/material";
import { Engagement } from "../api";

interface AttackChainsPanelProps {
  engagement: Engagement | null;
}

export default function AttackChainsPanel({ engagement }: AttackChainsPanelProps) {
  return (
    <Box>
      <Paper sx={{ p: 2, bgcolor: "#111827" }}>
        <Typography variant="subtitle2" sx={{ color: "#00e5ff" }}>
          Attack Chains
        </Typography>
        <Typography variant="body2" sx={{ color: "#9ca3af", mt: 1 }}>
          {engagement ? `Viewing chains for: ${engagement.target}` : "Select an engagement to view attack chains"}
        </Typography>
      </Paper>
    </Box>
  );
}
