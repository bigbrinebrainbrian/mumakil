<?php
$keyFile = __DIR__ . '/config/api_key.txt';
$AI_KEY = file_exists($keyFile) ? trim(file_get_contents($keyFile)) : '';

echo "<pre>";
echo "=== Testing Gemini 2.0 Flash ===\n\n";

// Use the available model from your list
$url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={$AI_KEY}";

$data = [
    "contents" => [[
        "parts" => [[
            "text" => "Say hello world in JSON format: {\"message\": \"hello\"}"
        ]]
    ]]
];

$context = stream_context_create([
    "http" => [
        "method" => "POST",
        "header" => "Content-Type: application/json",
        "content" => json_encode($data),
        "timeout" => 10
    ]
]);

echo "Testing gemini-2.0-flash...\n";
$response = @file_get_contents($url, false, $context);

if ($response === false) {
    echo "❌ Request failed\n";
    $error = error_get_last();
    print_r($error);
} else {
    $decoded = json_decode($response, true);
    if (isset($decoded['error'])) {
        echo "❌ API Error: " . $decoded['error']['message'] . "\n";
    } else {
        echo "✅ SUCCESS! Gemini 2.0 Flash is working!\n";
        echo "Response: " . ($decoded['candidates'][0]['content']['parts'][0]['text'] ?? 'No text') . "\n";
    }
}

echo "</pre>";
?>  