import React from "react";
import { Box, Paper, Typography, TextField, Button } from "@mui/material";

export default function SearchPanel() {
  return (
    <Box>
      <Paper sx={{ p: 2, bgcolor: "#111827" }}>
        <Typography variant="subtitle2" sx={{ color: "#00e5ff", mb: 2 }}>
          Attack Knowledge Search
        </Typography>
        <TextField
          fullWidth
          placeholder="Search attack knowledge base..."
          slotProps={{ htmlInput: { "data-search-input": "true" } }}
        />
        <Button variant="contained" sx={{ mt: 2 }}>
          Search
        </Button>
      </Paper>
    </Box>
  );
}
