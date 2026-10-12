FROM golang:1.22-alpine AS build
WORKDIR /src
COPY go.mod ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o /out/viewer .

FROM alpine:3.20
WORKDIR /app
COPY --from=build /out/viewer /usr/local/bin/viewer
EXPOSE 8080
ENV VIEWER_PORT=8080
CMD ["viewer"]
