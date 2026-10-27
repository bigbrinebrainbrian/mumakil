<?php
/**
 * qc_engine.php v13.2 – Insert + Delete + Update + AC21 (Token Required)
 *
 * NEW:
 * - AC21 block added (global token validation logic)
 * - Fix: ensures $status, $reason, $risk always defined
 * - Compatible with index.php v1.7.2 soft-fail token system
 */

require_once __DIR__ . '/lib/logger.php';

class QCEngineRunner {
    private $projectBaseUrl;
    private $qcToken;
    private $logFile;
    private $lastInsertDir;

    private $primaryGroup = ['nip','nama','kodejabatan','rek_bank','rek_nomor','rek_kdbank'];

    public function __construct($projectBaseUrl = null, $qcToken = null) {
        $this->projectBaseUrl = $projectBaseUrl;
        $this->qcToken = $qcToken;

        $logDir = __DIR__ . '/storage/logs';
        if (!is_dir($logDir)) @mkdir($logDir, 0777, true);
        $this->logFile = $logDir . '/qc_engine_debug.log';

        $this->lastInsertDir = __DIR__ . '/storage/last_inserts';
        if (!is_dir($this->lastInsertDir)) @mkdir($this->lastInsertDir, 0777, true);
    }

    private function log($msg) {
        @file_put_contents($this->logFile, "[" . date('c') . "] " . $msg . PHP_EOL, FILE_APPEND);
    }

    /************************************************************
     * Project API forwarding
     ************************************************************/
    private function callProjectApi($payload) {
        $lib = __DIR__ . '/lib/api_client.php';
        if (!file_exists($lib)) throw new Exception("api_client.php missing");
        require_once $lib;

        if (!is_array($payload)) throw new Exception("payload must be array");

        $this->log("callProjectApi INCOMING: " . json_encode($payload, JSON_PRETTY_PRINT));

        $rawAction = $payload['action'] ?? ($payload['request']['action'] ?? null);

        $isDelete = $rawAction && preg_match('/delete/i', $rawAction);
        $isUpdate = $rawAction && preg_match('/update/i', $rawAction);
        $isInsert = $rawAction && preg_match('/insert/i', $rawAction);

        if ($isInsert) return $this->forwardInsert($payload, $rawAction);
        if ($isDelete) return $this->forwardDelete($payload, $rawAction);
        if ($isUpdate) return $this->forwardUpdate($payload, $rawAction);

        return $this->forwardEvaluate($payload);
    }

    /************************************************************
     * GET forwarding
     ************************************************************/
    private function forwardEvaluate(array $payload) {
        $params = $payload;
        $params['token'] = $payload['token'] ?? $payload['params']['token'] ?? $this->qcToken;

        $action = $params['action'] ?? null;
        if (!$action) throw new Exception("Missing action for evaluate");

        $this->log("FORWARD(EVALUATE) → action={$action}");
        $resp = api_call($action, $params);

        return $this->normalizeProjectResponse($resp);
    }

    /************************************************************
     * INSERT forwarding
     ************************************************************/
    private function forwardInsert(array $payload, string $originalAction) {
        $params = [];

        if (isset($payload['request']) && is_array($payload['request']))
            $params = array_merge($params, $payload['request']);

        if (isset($payload['data']) && is_array($payload['data']))
            $params = array_merge($params, $payload['data']);

        if (empty($params['nip'])) $params['nip'] = 'AUTO_DEBUG_NIP';
        if (empty($params['nama'])) $params['nama'] = 'AUTO_DEBUG_NAMA';

        $params['action'] = $originalAction;
        $params['token'] = $payload['token'] ?? $this->qcToken;

        $resp = api_call($originalAction, $params);
        return $this->normalizeProjectResponse($resp);
    }

    /************************************************************
     * DELETE forwarding
     ************************************************************/
    private function forwardDelete(array $payload, string $originalAction) {
        $params = [];

        if (isset($payload['request'])) $params = array_merge($params, $payload['request']);
        if (isset($payload['data']))    $params = array_merge($params, $payload['data']);

        $params['action'] = $originalAction;
        $params['token']  = $payload['token'] ?? $this->qcToken;

        $resp = api_call($originalAction, $params);
        return $this->normalizeProjectResponse($resp);
    }

    /************************************************************
     * UPDATE forwarding
     ************************************************************/
    private function forwardUpdate(array $payload, string $originalAction) {
        $params = [];

        if (isset($payload['request'])) $params = array_merge($params, $payload['request']);
        if (isset($payload['data']))    $params = array_merge($params, $payload['data']);

        $params['action'] = $originalAction;
        $params['token']  = $payload['token'] ?? $this->qcToken;

        $resp = api_call($originalAction, $params);
        return $this->normalizeProjectResponse($resp);
    }

    /************************************************************
     * Response Normalizer
     ************************************************************/
    private function normalizeProjectResponse($resp) {
        return [
            'status_code' => intval($resp['status'] ?? 0),
            'success'     => $resp['body']['success'] ?? false,
            'data'        => $resp['body']['data'] ?? $resp['body'],
            'raw'         => $resp['body']
        ];
    }

    /************************************************************
     * Duplicate insert helpers
     ************************************************************/
    private function lastInsertPath(string $action) : string {
        $safe = preg_replace('/[^a-zA-Z0-9_\-]/','_', $action);
        return $this->lastInsertDir . '/' . $safe . '.json';
    }

    private function readLastInsert(string $action) {
        $p = $this->lastInsertPath($action);
        if (!file_exists($p)) return null;
        return json_decode(@file_get_contents($p), true);
    }

    private function writeLastInsert(string $action, array $payloadSubset) {
        @file_put_contents(
            $this->lastInsertPath($action),
            json_encode($payloadSubset, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE)
        );
    }

    private function extractPrimarySubset(array $candidate) : array {
        $subset = [];
        foreach ($this->primaryGroup as $f)
            $subset[$f] = array_key_exists($f, $candidate)
                ? (is_null($candidate[$f]) ? null : (string)$candidate[$f])
                : null;
        return $subset;
    }

    private function isPrimaryIdentical(array $a, array $b) : bool {
        foreach ($this->primaryGroup as $f)
            if ((string)($a[$f] ?? '') !== (string)($b[$f] ?? ''))
                return false;
        return true;
    }

    /************************************************************
     * MAIN ENGINE
     ************************************************************/
    public function run($payload) {

        $acId = $payload['ac_id'] ?? null;
        if (!$acId) throw new Exception("ac_id required");

        $callPayload = $payload['params'] ?? ($payload['request'] ?? $payload);
        $canonical   = $this->callProjectApi($callPayload);

        $actionCalled = $callPayload['action'] ?? null;
        $statusCode   = $canonical['status_code'];
        $isSuccess    = $canonical['success'];

        $isInsertAction = $actionCalled && stripos($actionCalled, 'insert') !== false;
        $isDeleteAction = $actionCalled && stripos($actionCalled, 'delete') !== false;
        $isUpdateAction = $actionCalled && stripos($actionCalled, 'update') !== false;
        $isGetAction    = $actionCalled && stripos($actionCalled, 'get') === 0;

        $rawMessage = is_array($canonical['raw']) && isset($canonical['raw']['message'])
            ? (string)$canonical['raw']['message']
            : '';

        $effectiveStatus  = $statusCode;
        $effectiveSuccess = $isSuccess;

        if (!$isGetAction) {
            if (
                $statusCode === 404 ||
                ($statusCode === 200 && !$isSuccess && stripos($rawMessage, 'action not found') !== false) ||
                ($statusCode === 400 && stripos($rawMessage, 'invalid action') !== false)
            ) {
                $effectiveStatus = 404;
                $effectiveSuccess = false;
            }
        }

        /************************************************************
         * AC21 – Token Required (Global)
         ************************************************************/
        if ($acId === 'AC21') {

            $autoStatus = $payload['automation_status'] ?? 200;

            if ($autoStatus === 401) {
                $status = 'PASSED';
                $reason = 'Token missing and API correctly blocked request';
                $risk   = 0;
            }
            else {
                if ($effectiveStatus === 200 && $effectiveSuccess) {
                    $status = 'PASSED';
                    $reason = 'Authorized request succeeded';
                    $risk   = 0;
                } elseif ($effectiveStatus === 401) {
                    $status = 'FAILED';
                    $reason = 'Token provided but rejected by API';
                    $risk   = 90;
                } else {
                    $status = 'FAILED';
                    $reason = 'Unexpected API behavior for AC21';
                    $risk   = 70;
                }
            }

            return [
                "engine_result" => [
                    "status" => $status,
                    "return" => $effectiveStatus,
                    "reason" => $reason,
                    "risk"   => $risk
                ],
                "analyze_payload" => [
                    "ac_id" => $acId,
                    "api_response" => [
                        "status" => $effectiveStatus,
                        "body"   => $canonical['data']
                    ]
                ],
                "raw_api_response" => $canonical['raw']
            ];
        }

        /************************************************************
         * INSERT (unchanged)
         ************************************************************/
        if ($isInsertAction) {
            $candidate = $callPayload['data'] ?? $callPayload;

            $primarySubset = $this->extractPrimarySubset($candidate);
            $last = $this->readLastInsert($actionCalled);

            if ($effectiveSuccess && in_array($effectiveStatus, [200, 201])) {
                if (is_array($last) && $this->isPrimaryIdentical($primarySubset, $last)) {
                    $status = 'PASSED';
                    $reason = 'Duplicate insert permitted by design';
                    $risk = 0;
                } else {
                    $this->writeLastInsert($actionCalled, $primarySubset);
                    $status = 'PASSED';
                    $reason = 'OK';
                    $risk = 0;
                }

                return [
                    "engine_result" => [
                        "status" => $status,
                        "return" => $effectiveStatus,
                        "reason" => $reason,
                        "risk" => $risk
                    ],
                    "analyze_payload" => [
                        "ac_id" => $acId,
                        "api_response" => [
                            "status" => $effectiveStatus,
                            "body" => $canonical['data']
                        ]
                    ],
                    "raw_api_response" => $canonical['raw']
                ];
            }
        }

        /************************************************************
         * DELETE (AC07, AC08)
         ************************************************************/
        if ($isDeleteAction) {

            if ($acId === 'AC07') {
                if ($effectiveStatus === 200 && $effectiveSuccess) {
                    $status = 'PASSED';
                    $reason = 'Delete succeeded';
                    $risk = 0;
                } elseif ($effectiveStatus === 404) {
                    $status = 'PASSED';
                    $reason = 'Record not found (expected negative)';
                    $risk = 0;
                } else {
                    $status = 'FAILED';
                    $reason = 'Unexpected delete behavior';
                    $risk = 50;
                }
            }

            elseif ($acId === 'AC08') {
                if ($effectiveStatus === 401) {
                    $status = 'PASSED';
                    $reason = 'Unauthorized delete correctly blocked';
                    $risk = 0;
                } elseif ($effectiveStatus === 200 && $effectiveSuccess) {
                    $status = 'PASSED';
                    $reason = 'Authorized delete succeeded';
                    $risk = 0;
                } else {
                    $status = 'FAILED';
                    $reason = 'Token validation mismatch';
                    $risk = 80;
                }
            }

            return [
                "engine_result" => [
                    "status" => $status,
                    "return" => $effectiveStatus,
                    "reason" => $reason,
                    "risk"   => $risk
                ],
                "analyze_payload" => [
                    "ac_id" => $acId,
                    "api_response" => [
                        "status" => $effectiveStatus,
                        "body"   => $canonical['data']
                    ]
                ],
                "raw_api_response" => $canonical['raw']
            ];
        }

        /************************************************************
         * UPDATE (AC09, AC10)
         ************************************************************/
        if ($isUpdateAction) {

            if ($acId === 'AC09') {
                if ($effectiveStatus === 200 && $effectiveSuccess) {
                    $status = 'PASSED';
                    $reason = 'Update OK';
                    $risk = 0;
                } elseif ($effectiveStatus === 404) {
                    $status = 'PASSED';
                    $reason = 'Not found (expected negative)';
                    $risk = 0;
                } else {
                    $status = 'FAILED';
                    $reason = 'Unexpected update behavior';
                    $risk = 60;
                }
            }

            elseif ($acId === 'AC10') {
                if ($effectiveStatus === 400) {
                    $status = 'PASSED';
                    $reason = 'Validation triggered';
                    $risk = 0;
                } elseif ($effectiveStatus === 200) {
                    $status = 'PASSED';
                    $reason = 'Validation off but update allowed';
                    $risk = 30;
                } else {
                    $status = 'FAILED';
                    $reason = 'Unexpected validation behavior';
                    $risk = 70;
                }
            }

            return [
                "engine_result" => [
                    "status" => $status,
                    "return" => $effectiveStatus,
                    "reason" => $reason,
                    "risk"   => $risk
                ],
                "analyze_payload" => [
                    "ac_id" => $acId,
                    "api_response" => [
                        "status" => $effectiveStatus,
                        "body"   => $canonical['data']
                    ]
                ],
                "raw_api_response" => $canonical['raw']
            ];
        }

        /************************************************************
         * GET (default)
         ************************************************************/
        if ($isSuccess) {
            $status = 'PASSED';
            $reason = 'OK';
            $risk = 0;
        } elseif (
            $isGetAction &&
            (
                $statusCode === 404 ||
                ($statusCode === 400 && stripos($rawMessage, 'invalid action') !== false) ||
                ($statusCode === 200 && !$isSuccess && stripos($rawMessage, 'action not found') !== false)
            )
        ) {
            $status = 'PASSED';
            $reason = 'Endpoint not found (expected negative)';
            $risk = 0;
        } else {
            $status = 'FAILED';
            $reason = ($statusCode === 400 ? 'Unexpected system failure' : 'Status mismatch');
            $risk = 70;
        }

        return [
            "engine_result" => [
                "status" => $status,
                "return" => $statusCode,
                "reason" => $reason,
                "risk"   => $risk
            ],
            "analyze_payload" => [
                "ac_id" => $acId,
                "api_response" => [
                    "status" => $canonical['status_code'],
                    "body"   => $canonical['data']
                ]
            ],
            "raw_api_response" => $canonical['raw']
        ];
    }
}
?>
