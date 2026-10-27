<?php
// ACES v1.3 – analyze.php
//note: Updated for AC07–AC10 (Delete + Update reasoning)

//
// --------------------------------------------------------
// Helpers
// --------------------------------------------------------
function ts() { return date('d/m/Y H:i'); }

function send_json($code, $payload) {
    http_response_code($code);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($payload, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
    exit;
}

//
// --------------------------------------------------------
// Load API Key
// --------------------------------------------------------
$keyFile = __DIR__ . '/config/api_key.txt';
$AI_KEY = file_exists($keyFile) ? trim(file_get_contents($keyFile)) : '';

if (!$AI_KEY) {
    send_json(500, [
        "success" => false,
        "reason" => "Missing Gemini API Key",
        "severity" => "high",
        "risk_tags" => ["ai_unavailable"]
    ]);
}

//
// --------------------------------------------------------
// Parse Input
// --------------------------------------------------------
$raw = file_get_contents('php://input');
$input = json_decode($raw, true);

if (!is_array($input)) {
    send_json(400, [
        "success" => false,
        "reason" => "Invalid input JSON",
        "severity" => "high",
        "risk_tags" => ["schema_error"]
    ]);
}

//
// --------------------------------------------------------
// AI prompt untuk reasoning
// --------------------------------------------------------
$prompt = <<<PROMPT
You are ACES v1.3 AI reasoning module.

Your job:
- Read deterministic QC result + API response
- Produce STRICT JSON with fields:

{
"success": true,
"findings": [
    { "rule": "...", "result": "pass/fail", "details": "..." }
],
"severity": "low|medium|high",
"risk_tags": ["..."],
"reason": "Short strong explanation"
}

Rules:
- Findings must list each important issue.
- If table is empty → reason must be: "Table returned 0 rows. Expected non-empty dataset based on AC rule."
- Severity must reflect seriousness.
- risk_tags: provide strong classification tags.
- DO NOT include anything outside JSON.

Additional AC-specific reasoning rules:   //note: AC07–AC10 added
- For DELETE actions:
    - 200 + success:true → "Delete succeeded"
    - 404 → "Record not found" (expected negative for AC07)
    - 401 → "Unauthorized" (expected for AC08 when token missing)

- For UPDATE actions:
    - 200 + success:true → "Update successful" (found)
    - 404 → "Update target not found" (expected in AC09 negative case)
    - 400 → "Validation error" (expected for AC10 when validation=ON)

- Your output must always stay in JSON.
- DO NOT add commentary. DO NOT explain outside the JSON.

INPUT:
PROMPT;

$payload_to_ai = $prompt . "\n" . json_encode($input, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);

//
// --------------------------------------------------------
// Call Gemini (stable)
// --------------------------------------------------------
$url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={$AI_KEY}";

$payload = [
    "contents" => [["parts" => [["text" => $payload_to_ai]]]]
];

$opts = [
    "http" => [
        "method" => "POST",
        "header" => "Content-Type: application/json\r\n",
        "content" => json_encode($payload),
        "timeout" => 15
    ]
];

$ctx = stream_context_create($opts);
$result = @file_get_contents($url, false, $ctx);

if ($result === false) {
    send_json(500, [
        "success" => false,
        "findings" => [],
        "severity" => "high",
        "risk_tags" => ["ai_failure"],
        "reason" => "AI request failed"
    ]);
}

//
// --------------------------------------------------------
// Parse AI output
// --------------------------------------------------------
$decoded = json_decode($result, true);
$text = $decoded['candidates'][0]['content']['parts'][0]['text'] ?? '';

$ai = json_decode($text, true);

//note: fallback raw JSON extraction
if (!$ai && preg_match('/\{.*\}/s', $text, $m)) {
    $ai = json_decode($m[0], true);
}

if (!$ai) {
    send_json(500, [
        "success" => false,
        "findings" => [],
        "severity" => "high",
        "risk_tags" => ["ai_invalid_json"],
        "reason" => "AI returned invalid JSON"
    ]);
}

//
// --------------------------------------------------------
// Final Output
// --------------------------------------------------------
$ai['success'] = true;
$ai['evaluated_at'] = ts();

send_json(200, $ai);
?>
