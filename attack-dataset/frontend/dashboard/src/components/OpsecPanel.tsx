import React from "react";
import { Box, Paper, Typography } from "@mui/material";
import { Engagement } from "../api";

interface OpsecPanelProps {
  engagement: Engagement | null;
}

export default function OpsecPanel({ engagement }: OpsecPanelProps) {
  return (
    <Box>
      <Paper sx={{ p: 2, bgcolor: "#111827" }}>
        <Typography variant="subtitle2" sx={{ color: "#00e5ff" }}>
          OpSec Assessment
        </Typography>
        <Typography variant="body2" sx={{ color: "#9ca3af", mt: 1 }}>
          {engagement ? `OpSec report for: ${engagement.target}` : "Select an engagement to view OpSec assessment"}
        </Typography>
      </Paper>
    </Box>
  );
}
