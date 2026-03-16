package liveingest

import (
	"bytes"
	"context"
	"crypto/tls"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

type ClickHouseClient struct {
	cfg        ClickHouseConfig
	httpClient *http.Client
}

func NewClickHouseClient(cfg ClickHouseConfig) *ClickHouseClient {
	transport := &http.Transport{}
	if cfg.Secure && !cfg.VerifyTLS {
		transport.TLSClientConfig = &tls.Config{InsecureSkipVerify: true}
	}

	return &ClickHouseClient{
		cfg: cfg,
		httpClient: &http.Client{
			Timeout:   cfg.ConnectTimeout + cfg.SendReceiveTimeout,
			Transport: transport,
		},
	}
}

func (c *ClickHouseClient) InsertRows(ctx context.Context, table string, rows []any) error {
	if len(rows) == 0 {
		return nil
	}

	var buffer bytes.Buffer
	buffer.WriteString("INSERT INTO ")
	buffer.WriteString(c.cfg.Database)
	buffer.WriteByte('.')
	buffer.WriteString(table)
	buffer.WriteString(" FORMAT JSONEachRow\n")
	encoder := json.NewEncoder(&buffer)
	encoder.SetEscapeHTML(false)
	for _, row := range rows {
		if err := encoder.Encode(row); err != nil {
			return fmt.Errorf("encode %s row: %w", table, err)
		}
	}

	scheme := "http"
	if c.cfg.Secure {
		scheme = "https"
	}
	endpoint := url.URL{
		Scheme:   scheme,
		Host:     fmt.Sprintf("%s:%d", c.cfg.Host, c.cfg.Port),
		Path:     "/",
		RawQuery: "database=" + url.QueryEscape(c.cfg.Database),
	}

	request, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint.String(), &buffer)
	if err != nil {
		return fmt.Errorf("build clickhouse request: %w", err)
	}

	request.Header.Set("Accept", "application/json")
	request.Header.Set("Content-Type", "text/plain; charset=utf-8")
	request.Header.Set("Authorization", "Basic "+base64.StdEncoding.EncodeToString([]byte(c.cfg.User+":"+c.cfg.Password)))

	response, err := c.httpClient.Do(request)
	if err != nil {
		return fmt.Errorf("insert into %s: %w", table, err)
	}
	defer response.Body.Close()

	if response.StatusCode < 200 || response.StatusCode >= 300 {
		body, _ := io.ReadAll(io.LimitReader(response.Body, 4096))
		return fmt.Errorf("insert into %s failed with %s: %s", table, response.Status, strings.TrimSpace(string(body)))
	}
	return nil
}

func retryDelay(attempt int, maxDelay time.Duration) time.Duration {
	delay := 500 * time.Millisecond
	for i := 1; i < attempt; i++ {
		delay *= 2
		if delay >= maxDelay {
			return maxDelay
		}
	}
	if delay > maxDelay {
		return maxDelay
	}
	return delay
}
