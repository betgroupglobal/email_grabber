import React, { useState } from "react";
import {
  Box, TextField, Button, Paper, Typography,
  Chip, Accordion, AccordionSummary, AccordionDetails,
  CircularProgress,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { semanticSearch, AttackRecord } from "../api";

interface SearchResult { record: AttackRecord; score: number; }

export default function SearchPanel() {
  const [query, setQuery]     = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);

  const doSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const data = await semanticSearch(query, 15);
      setResults(data.results || []);
    } finally {
      setLoading(false);
    }
  };

  const severityChip = (score: number) => {
    if (score >= 0.8) return <Chip label={`${(score * 100).toFixed(0)}% match`} color="error" size="small" />;
    if (score >= 0.6) return <Chip label={`${(score * 100).toFixed(0)}% match`} color="warning" size="small" />;
    return <Chip label={`${(score * 100).toFixed(0)}% match`} size="small" />;
  };

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <Paper sx={{ p: 2, bgcolor: "#111827" }}>
        <Typography variant="subtitle2" sx={{ color: "#00e5ff", mb: 1 }}>
          Semantic Attack Search
        </Typography>
        <Box sx={{ display: "flex", gap: 1 }}>
          <TextField
            size="small" fullWidth
            placeholder="e.g. Apache web server on Linux with SSH exposed"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && doSearch()}
            sx={{ "& .MuiOutlinedInput-root": { fontFamily: "monospace" } }}
          />
          <Button variant="contained" onClick={doSearch} disabled={loading}>
            {loading ? <CircularProgress size={18} /> : "Search"}
          </Button>
        </Box>
      </Paper>

      {results.map((r, i) => (
        <Accordion key={r.record.id} sx={{ bgcolor: "#111827" }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Box sx={{ display: "flex", gap: 1, alignItems: "center", flexWrap: "wrap", flex: 1 }}>
              {severityChip(r.score)}
              <Typography variant="body2" sx={{ fontWeight: 600 }}>{r.record.title}</Typography>
              <Chip label={r.record.category} size="small" variant="outlined" />
              {r.record.mitre_technique && (
                <Chip label={r.record.mitre_technique.split(",")[0].trim()} size="small" color="info" variant="outlined" />
              )}
            </Box>
          </AccordionSummary>
          <AccordionDetails>
            <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
              <Box>
                <Typography variant="caption" sx={{ color: "#6b7280" }}>ATTACK TYPE</Typography>
                <Typography variant="body2">{r.record.attack_type}</Typography>
              </Box>
              <Box>
                <Typography variant="caption" sx={{ color: "#6b7280" }}>TOOLS</Typography>
                <Typography variant="body2" sx={{ fontFamily: "monospace", fontSize: "0.75rem" }}>
                  {r.record.tools_used}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" sx={{ color: "#6b7280" }}>IMPACT</Typography>
                <Typography variant="body2">{r.record.impact}</Typography>
              </Box>
              <Box>
                <Typography variant="caption" sx={{ color: "#6b7280" }}>DETECTION</Typography>
                <Typography variant="body2">{r.record.detection_method}</Typography>
              </Box>
              <Box>
                <Typography variant="caption" sx={{ color: "#6b7280" }}>SOLUTION</Typography>
                <Typography variant="body2">{r.record.solution}</Typography>
              </Box>
            </Box>
          </AccordionDetails>
        </Accordion>
      ))}

      {results.length === 0 && !loading && (
        <Paper sx={{ p: 4, bgcolor: "#111827", textAlign: "center" }}>
          <Typography sx={{ color: "#6b7280" }}>
            Search the 14k+ attack knowledge base by natural language.
          </Typography>
        </Paper>
      )}
    </Box>
  );
}
