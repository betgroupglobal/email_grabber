FROM golang:1.22-alpine AS builder

RUN apk add --no-cache git
WORKDIR /src
COPY go.mod go.sum* ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o /analyzer .

# ── runtime ───────────────────────────────────────────────────────────────────
FROM alpine:3.19

RUN apk add --no-cache nmap ca-certificates

COPY --from=builder /analyzer /usr/local/bin/analyzer

EXPOSE 8001

ENTRYPOINT ["/usr/local/bin/analyzer"]
