<?php

// ACES v1.7.2 – automation_dbmigas/index.php
// Soft-fail token: allows AI reasoning + QC engine even when token missing

function sendResponse($success, $data = null, $message = '', $statusCode = 200) {
    header('Content-Type: application/json');
    http_response_code($statusCode);
    $resp = ['success' => $success, 'message' => $message];
    if ($data !== null) $resp['data'] = $data;
    echo json_encode($resp, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
    exit;
}

function log_app($tag, $payload = null) {
    $dir = __DIR__ . '/storage/logs';
    if (!is_dir($dir)) @mkdir($dir, 0777, true);
    file_put_contents($dir . '/app.log',
        json_encode(['ts'=>gmdate('c'), 'tag'=>$tag, 'data'=>$payload],
        JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . PHP_EOL,
        FILE_APPEND);
}

function audit_log($tag, $payload = null) {
    $dir = __DIR__ . '/storage/logs';
    if (!is_dir($dir)) @mkdir($dir, 0777, true);
    file_put_contents($dir . '/audit.log',
        json_encode(['ts'=>date('d/m/Y H:i'), 'name'=>$tag, 'data'=>$payload],
        JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . PHP_EOL,
        FILE_APPEND);
}

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') exit(200);
if ($_SERVER['REQUEST_METHOD'] !== 'POST')
    sendResponse(false, null, 'Method not allowed', 405);

$raw = file_get_contents('php://input');
$input = json_decode($raw, true);
if (!is_array($input)) sendResponse(false, null, 'Invalid JSON', 400);

// Load QC Token
$token = $input['token'] ?? null;
$tokenFile = __DIR__ . '/config/qc_token.txt';
$expectedToken = file_exists($tokenFile) ? trim(file_get_contents($tokenFile)) : 'qc-default-token';

// PATCH v1.7.2 — SOFT FAIL (NO EXIT)
$automationStatus = 200;
if (!$token || $token !== $expectedToken) {
    audit_log('unauthorized_request', ['input'=>$input]);
    $automationStatus = 401; // unauthorized but DO NOT EXIT
}

// Required action
$action = $input['action'] ?? '';
if (!$action) sendResponse(false, null, 'Action is required', 400);
audit_log('action_received', ['action' => $action]);

require_once __DIR__ . '/qc_engine.php';

switch ($action) {

    case 'ListACs':
        $file = __DIR__ . '/testcases/ac_registry.json';
        $list = file_exists($file) ? json_decode(file_get_contents($file), true) : [];
        sendResponse(true, $list, 'AC registry loaded', 200);
        break;

    case 'EvaluateAC':

        $payload = $input['payload'] ?? null;
        if (!$payload || !isset($payload['ac_id']))
            sendResponse(false, null, 'Missing payload or ac_id', 400);

        // Convert "request" → "params" for backward compatibility
        if (isset($payload['request'])) {
            $payload['params'] = $payload['request'];
            unset($payload['request']);
        }

        // Ensure params exists
        if (!isset($payload['params']) || !is_array($payload['params'])) {
            $payload['params'] = [];
        }

        // Always set token (even invalid empty one)
        $payload['params']['token'] = $token;

        // Insert automation token status for qc_engine
        $payload['automation_status'] = $automationStatus;

        // Initialize QC engine
        $engine = new QCEngineRunner(
            "http://localhost/project_dbmigas/index.php",
            $expectedToken
        );

        // Run deterministic QC
        $det = $engine->run($payload);
        $useAI = $input['use_ai'] ?? true;

        if (!$useAI) {
            sendResponse(true, ["deterministic" => $det['engine_result']], "AC evaluation OK", 200);
        }

        // Send to analyze.php
        $aiPayload = $det['analyze_payload'];
        $aiPayload['token'] = $token;

        $body = json_encode($aiPayload);
        $ch = curl_init("http://localhost/automation_dbmigas/analyze.php");
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_POST           => true,
            CURLOPT_HTTPHEADER     => ["Content-Type: application/json"],
            CURLOPT_POSTFIELDS     => $body,
            CURLOPT_TIMEOUT        => 30
        ]);
        $raw_ai = curl_exec($ch);
        curl_close($ch);

        $aiResult = $raw_ai ? json_decode($raw_ai, true) : null;
        if (!$aiResult) {
            $aiResult = ["success"=>false,"reason"=>"AI unavailable","severity"=>"high","risk_tags"=>["ai_failure"]];
        }

        $det['engine_result']['AI_reasoning'] = $aiResult['reason'] ?? "No AI reasoning";

        sendResponse(
            true,
            [
                "combined"      => $det['engine_result'],
                "deterministic" => $det['engine_result'],
                "ai_reasoning"  => $aiResult
            ],
            "AC evaluation completed with AI",
            200
        );
        break;

    default:
        sendResponse(false, null, 'Invalid action', 400);
}
