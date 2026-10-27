<?php
/**
 * api_client.php  (patched v1.8 — TOKEN FIX + SAFE ACTION + DEBUG LOGS)
 */

require_once __DIR__ . '/logger.php';

$TOKEN_FILE = __DIR__ . '/../config/qc_token.txt';

/* -------------------------------------------------
 * RAW TOKEN READ + BYTE DEBUG
 * ------------------------------------------------- */
$raw = @file_get_contents($TOKEN_FILE);

// Log raw bytes
$hex_raw = implode(' ', str_split(bin2hex((string)$raw), 2));
file_put_contents(__DIR__ . '/../storage/logs/api_client_debug.log', "[" . date('c') . "] RAW_TOKEN_BYTES: $hex_raw\n", FILE_APPEND);
file_put_contents(__DIR__ . '/../storage/logs/api_client_debug.log', "[" . date('c') . "] RAW_TOKEN_STRING: '" . $raw . "'\n", FILE_APPEND);
file_put_contents(__DIR__ . '/../storage/logs/api_client_debug.log', "[" . date('c') . "] RAW_LENGTH: " . strlen((string)$raw) . "\n", FILE_APPEND);

// Trim token
$QC_TOKEN = trim((string)$raw);

// Log trimmed bytes
$hex_trim = implode(' ', str_split(bin2hex((string)$QC_TOKEN), 2));
file_put_contents(__DIR__ . '/../storage/logs/api_client_debug.log', "[" . date('c') . "] TRIMMED_TOKEN_BYTES: $hex_trim\n", FILE_APPEND);
file_put_contents(__DIR__ . '/../storage/logs/api_client_debug.log', "[" . date('c') . "] INTERNAL_QC_TOKEN: '" . $QC_TOKEN . "'\n", FILE_APPEND);

// Force fail if token empty
if ($QC_TOKEN === "" || $QC_TOKEN === null) {
    file_put_contents(__DIR__ . '/../storage/logs/api_client_debug.log', "[" . date('c') . "] ERROR: QC_TOKEN EMPTY AFTER TRIM()\n", FILE_APPEND);
    throw new Exception("QC Token unreadable — hidden bytes detected in qc_token.txt");
}

// Log file load
file_put_contents(__DIR__ . '/../storage/logs/api_client_debug.log', "[" . date('c') . "] api_client.php LOADED FROM: " . __FILE__ . "\n", FILE_APPEND);


/**
 * MAIN CLIENT FUNCTION (FIXED)
 */
function api_call(string $action, array $params = [])
{
    global $QC_TOKEN;

    static $CACHED_QC_TOKEN = null;
    if ($CACHED_QC_TOKEN === null && $QC_TOKEN !== "") {
        $CACHED_QC_TOKEN = $QC_TOKEN;
    }
    // Never allow overwrite cache with an empty string
    if ($QC_TOKEN === "" && $CACHED_QC_TOKEN !== "") {
        $QC_TOKEN = $CACHED_QC_TOKEN;
    }

    file_put_contents(__DIR__ . '/../storage/logs/api_client_debug.log',
        "[" . date('c') . "] INTERNAL_QC_TOKEN (CALL TIME): '" . $QC_TOKEN . "'\n",
        FILE_APPEND
    );

    $url = "http://localhost/project_dbmigas/index.php";

    /* -------------------------------------------------
     * NUCLEAR #1 — unwrap nested `request`
     * ------------------------------------------------- */
    if (isset($params['request']) && is_array($params['request'])) {
        file_put_contents(
            __DIR__ . '/../storage/logs/api_client_debug.log',
            "[" . date('c') . "] NUCLEAR#1 UNWRAP: " . json_encode($params['request']) . "\n",
            FILE_APPEND
        );
        $params = $params['request'];
    }

    /* -------------------------------------------------
     * Prevent token poisoning (URL becomes token)
     * ------------------------------------------------- */
    if (isset($params['token']) && strpos($params['token'], "http://") === 0) {
        unset($params['token']);
    }

    /* -------------------------------------------------
     * Build final payload
     * ------------------------------------------------- */
    unset($params['request']); // hard remove wrapper only

    $payload = array_merge($params, [
        "action" => $action,
        "token"  => $params['token'] ?? $CACHED_QC_TOKEN
    ]);

    // Log outgoing payload
    file_put_contents(
        __DIR__ . '/../storage/logs/api_client_debug.log',
        "[" . date('c') . "] OUTGOING_PAYLOAD: " . json_encode($payload) . "\n",
        FILE_APPEND
    );

    $jsonBody = json_encode($payload, JSON_UNESCAPED_SLASHES);

    /* -------------------------------------------------
     * cURL request
     * ------------------------------------------------- */
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_POST           => true,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_HTTPHEADER     => ["Content-Type: application/json"],
        CURLOPT_POSTFIELDS     => $jsonBody,
        CURLOPT_TIMEOUT        => 10,
    ]);

    $rawResponse = curl_exec($ch);
    $httpCode    = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $curlErr     = curl_error($ch);
    curl_close($ch);

    // Log response
    file_put_contents(
        __DIR__ . '/../storage/logs/api_client_debug.log',
        "[" . date('c') . "] HTTP_CODE=$httpCode CURLERR=$curlErr\n[" . date('c') . "] RAW_RESPONSE: " . $rawResponse . "\n\n",
        FILE_APPEND
    );

    if ($rawResponse === false || $curlErr) {
        return [
            "status" => 0,
            "body"   => null,
            "error"  => "Connection failed: $curlErr"
        ];
    }

    $decoded = json_decode($rawResponse, true);

    if (json_last_error() !== JSON_ERROR_NONE) {
        file_put_contents(__DIR__ . '/../storage/logs/api_client_debug.log',
            "[" . date('c') . "] NUCLEAR#4 NONJSON_RESPONSE\n",
            FILE_APPEND
        );
        return [
            "status" => 200,
            "body" => [
                "success"      => false,
                "error_code"   => 404,
                "message"      => "QC-SIMULATED 404: Backend returned invalid output",
                "raw_response" => $rawResponse
            ],
            "error" => null
        ];
    }

    return [
        "status" => $httpCode,
        "body"   => $decoded,
        "error"  => null
    ];
}
?>
