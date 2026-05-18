import React from "react";
import { Box, Paper, Typography } from "@mui/material";
import { Engagement } from "../api";

interface EngagementPanelProps {
  active: Engagement | null;
  onNew: (engagement: Engagement) => void;
}

export default function EngagementPanel({ active, onNew }: EngagementPanelProps) {
  return (
    <Box>
      <Paper sx={{ p: 2, bgcolor: "#111827" }}>
        <Typography variant="subtitle2" sx={{ color: "#00e5ff" }}>
          Engagements Panel
        </Typography>
        <Typography variant="body2" sx={{ color: "#9ca3af", mt: 1 }}>
          {active ? `Active engagement: ${active.target}` : "No active engagement selected"}
        </Typography>
      </Paper>
    </Box>
  );
}
