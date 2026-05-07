import React from "react";
import {
  Box, Paper, Typography, Chip, Alert, LinearProgress,
  Accordion, AccordionSummary, AccordionDetails,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { Engagement, OpsecFinding } from "../api";

interface Props { engagement: Engagement | null; }

const SEV_COLOR: Record<string, "error" | "warning" | "info" | "success"> = {
  critical: "error", high: "error", medium: "warning", low: "info", info: "success",
};

function FindingRow({ f }: { f: OpsecFinding }) {
  return (
    <Accordion sx={{ bgcolor: "#0d1117" }}>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Box sx={{ display: "flex", gap: 1, alignItems: "center", flex: 1 }}>
          <Chip
            label={f.severity.toUpperCase()}
            size="small"
            color={SEV_COLOR[f.severity] || "default"}
          />
          <Typography variant="body2">{f.title}</Typography>
          <Chip label={f.rule_id} size="small" variant="outlined" sx={{ ml: "auto", fontSize: "0.6rem" }} />
        </Box>
      </AccordionSummary>
      <AccordionDetails>
        <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
          <Box>
            <Typography variant="caption" sx={{ color: "#6b7280" }}>DESCRIPTION</Typography>
            <Typography variant="body2">{f.description}</Typography>
          </Box>
          <Box>
            <Typography variant="caption" sx={{ color: "#6b7280" }}>REMEDIATION</Typography>
            <Typography variant="body2" sx={{ color: "#10b981" }}>{f.remediation}</Typography>
          </Box>
          {f.evidence && (
            <Box>
              <Typography variant="caption" sx={{ color: "#6b7280" }}>EVIDENCE</Typography>
              <Typography variant="body2" sx={{ fontFamily: "monospace", fontSize: "0.72rem" }}>{f.evidence}</Typography>
            </Box>
          )}
        </Box>
      </AccordionDetails>
    </Accordion>
  );
}

export default function OpsecPanel({ engagement }: Props) {
  const report = engagement?.opsec_reports;

  if (!engagement) {
    return (
      <Paper sx={{ p: 4, bgcolor: "#111827", textAlign: "center" }}>
        <Typography sx={{ color: "#6b7280" }}>Select an engagement to view OpSec assessment.</Typography>
      </Paper>
    );
  }

  if (!report) {
    return (
      <Paper sx={{ p: 4, bgcolor: "#111827", textAlign: "center" }}>
        <Typography sx={{ color: "#6b7280" }}>
          {engagement.status === "complete"
            ? "No OpSec report available."
            : `Status: ${engagement.status} — OpSec report will appear when chains are ready.`}
        </Typography>
      </Paper>
    );
  }

  const scoreColor = report.risk_score >= 70 ? "#ef4444" : report.risk_score >= 40 ? "#f59e0b" : "#10b981";

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {/* Score banner */}
      <Paper sx={{ p: 2, bgcolor: "#111827" }}>
        <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 1 }}>
          <Typography variant="subtitle2" sx={{ color: "#00e5ff" }}>
            OpSec Risk Score
          </Typography>
          <Typography variant="h4" sx={{ color: scoreColor, fontFamily: "monospace" }}>
            {report.risk_score}<span style={{ fontSize: "1rem", color: "#6b7280" }}>/100</span>
          </Typography>
        </Box>
        <LinearProgress
          variant="determinate"
          value={report.risk_score}
          sx={{
            height: 8, borderRadius: 4,
            bgcolor: "#1f2937",
            "& .MuiLinearProgress-bar": { bgcolor: scoreColor },
          }}
        />
        <Box sx={{ display: "flex", gap: 1, mt: 1, flexWrap: "wrap" }}>
          {report.total_findings > 0 && (
            <>
              {(report as any).critical > 0 && <Chip label={`${(report as any).critical} critical`} size="small" color="error" />}
              {(report as any).high > 0    && <Chip label={`${(report as any).high} high`}    size="small" color="error" variant="outlined" />}
              {(report as any).medium > 0  && <Chip label={`${(report as any).medium} medium`} size="small" color="warning" />}
              {(report as any).low > 0     && <Chip label={`${(report as any).low} low`}     size="small" color="info" />}
            </>
          )}
        </Box>
      </Paper>

      {/* Global findings */}
      <Typography variant="subtitle2" sx={{ color: "#6b7280" }}>
        {report.global_findings.length} Unique Finding{report.global_findings.length !== 1 ? "s" : ""}
      </Typography>
      {report.global_findings.map((f, i) => <FindingRow key={i} f={f} />)}

      {report.global_findings.length === 0 && (
        <Alert severity="success">No OpSec findings detected. Attack plan looks clean.</Alert>
      )}
    </Box>
  );
}
