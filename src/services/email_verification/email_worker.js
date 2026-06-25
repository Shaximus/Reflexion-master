/**
 * Cloudflare Email Worker - Verification Code Extractor
 *
 * Receives incoming email via Cloudflare Email Routing,
 * extracts verification codes, and POSTs to the local webhook.
 *
 * Environment variables (set in wrangler.toml or dashboard):
 *   WEBHOOK_URL  - The endpoint to POST extracted data to
 *   WEBHOOK_SECRET - Shared secret for authenticating webhook calls
 */

// Patterns ordered by specificity - most specific first
const CODE_PATTERNS = [
  /(?:verification|confirm(?:ation)?|security|auth(?:entication)?)\s*code\s*(?:is\s*:?|:)\s*(\d{6})\b/i,
  /(?:your|the)\s*code\s*(?:is\s*:?|:)\s*(\d{6})\b/i,
  /(?:enter|use|input)\s+(?:this\s+)?code\s*:?\s*(\d{6})\b/i,
  /(?:one[- ]time\s*(?:pass(?:code|word)?|code)|OTP|PIN)\s*(?:is\s*:?|:)\s*(\d{6})\b/i,
  // HTML patterns: code in styled spans/divs (common in verification emails)
  /<[^>]*(?:class|style)[^>]*>\s*(\d{6})\s*<\//i,
  // Standalone 6-digit number on its own line (last resort)
  /^\s*(\d{6})\s*$/m,
];

/**
 * Strip HTML tags and decode common entities.
 */
function htmlToText(html) {
  return html
    .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, "")
    .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, "")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/(?:p|div|tr|li|h[1-6])>/gi, "\n")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(parseInt(n)))
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * Extract a 6-digit verification code from email text.
 * Tries specific patterns first, falls back to generic.
 */
function extractCode(text) {
  for (const pattern of CODE_PATTERNS) {
    const match = text.match(pattern);
    if (match) return match[1];
  }
  return null;
}

/**
 * Parse a raw MIME email into its parts.
 * Handles multipart/alternative and multipart/mixed.
 */
function parseMime(raw) {
  const headers = {};
  const headerEnd = raw.indexOf("\r\n\r\n");
  if (headerEnd === -1) return { headers, textBody: raw, htmlBody: null };

  const headerBlock = raw.substring(0, headerEnd);
  const body = raw.substring(headerEnd + 4);

  // Parse headers (handle folded lines)
  const unfolded = headerBlock.replace(/\r\n[ \t]+/g, " ");
  for (const line of unfolded.split("\r\n")) {
    const colon = line.indexOf(":");
    if (colon > 0) {
      const name = line.substring(0, colon).trim().toLowerCase();
      const value = line.substring(colon + 1).trim();
      headers[name] = value;
    }
  }

  const contentType = headers["content-type"] || "text/plain";

  // Decode transfer encoding
  function decodeBody(raw, encoding) {
    encoding = (encoding || "").toLowerCase().trim();
    if (encoding === "base64") {
      try {
        return atob(raw.replace(/\s/g, ""));
      } catch {
        return raw;
      }
    }
    if (encoding === "quoted-printable") {
      return raw
        .replace(/=\r?\n/g, "")
        .replace(/=([0-9A-Fa-f]{2})/g, (_, hex) =>
          String.fromCharCode(parseInt(hex, 16))
        );
    }
    return raw;
  }

  // Simple (non-multipart)
  if (!contentType.includes("multipart")) {
    const decoded = decodeBody(body, headers["content-transfer-encoding"]);
    if (contentType.includes("text/html")) {
      return { headers, textBody: htmlToText(decoded), htmlBody: decoded };
    }
    return { headers, textBody: decoded, htmlBody: null };
  }

  // Multipart: find boundary
  const boundaryMatch = contentType.match(/boundary="?([^";\s]+)"?/i);
  if (!boundaryMatch) return { headers, textBody: body, htmlBody: null };

  const boundary = boundaryMatch[1];
  const parts = body.split(`--${boundary}`);

  let textBody = null;
  let htmlBody = null;

  for (const part of parts) {
    if (part.startsWith("--") || part.trim() === "") continue;

    const partHeaderEnd = part.indexOf("\r\n\r\n");
    if (partHeaderEnd === -1) continue;

    const partHeaders = part.substring(0, partHeaderEnd).toLowerCase();
    const partBody = part.substring(partHeaderEnd + 4).replace(/\r\n$/, "");

    const encodingMatch = partHeaders.match(
      /content-transfer-encoding:\s*(\S+)/i
    );
    const encoding = encodingMatch ? encodingMatch[1] : "";
    const decoded = decodeBody(partBody, encoding);

    if (partHeaders.includes("text/html")) {
      htmlBody = decoded;
      if (!textBody) textBody = htmlToText(decoded);
    } else if (partHeaders.includes("text/plain")) {
      textBody = decoded;
    }
  }

  return { headers, textBody: textBody || "", htmlBody };
}

/**
 * Decode RFC 2047 encoded-words in subjects/headers.
 */
function decodeRfc2047(str) {
  return str.replace(/=\?([^?]+)\?([BbQq])\?([^?]+)\?=/g, (_, charset, encoding, data) => {
    if (encoding.toUpperCase() === "B") {
      try { return atob(data); } catch { return data; }
    }
    // Q encoding
    return data
      .replace(/_/g, " ")
      .replace(/=([0-9A-Fa-f]{2})/g, (__, hex) =>
        String.fromCharCode(parseInt(hex, 16))
      );
  });
}

export default {
  async email(message, env) {
    const webhookUrl = env.WEBHOOK_URL;
    const webhookSecret = env.WEBHOOK_SECRET || "";

    if (!webhookUrl) {
      console.error("WEBHOOK_URL not configured");
      message.setReject("Server misconfigured");
      return;
    }

    try {
      // Read the raw email
      const rawEmail = await new Response(message.raw).text();
      const { headers, textBody, htmlBody } = parseMime(rawEmail);

      // Decode subject
      const subject = decodeRfc2047(headers["subject"] || "(no subject)");

      // Try to extract code from text body first, then HTML
      let code = null;
      if (textBody) code = extractCode(textBody);
      if (!code && htmlBody) code = extractCode(htmlBody);

      const payload = {
        to: message.to,
        from: message.from,
        subject,
        code,
        raw_body: (textBody || htmlBody || "").substring(0, 10000),
        received_at: new Date().toISOString(),
      };

      const response = await fetch(webhookUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Webhook-Secret": webhookSecret,
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        console.error(`Webhook failed: ${response.status} ${await response.text()}`);
      }
    } catch (err) {
      console.error(`Email processing error: ${err.message}`);
    }
  },
};
