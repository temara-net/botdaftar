<?php
// Klien AI multi-provider: gemini | openai | openrouter.
// Provider DIPILIH di config.php oleh pemilik bot — tidak ada default bawaan.

class AIException extends Exception {}

class AIClient
{
    private string $provider;
    private string $apiKey;
    private string $model;
    private string $systemPrompt;
    private ?string $baseUrl;

    public function __construct(array $cfg)
    {
        $this->provider = strtolower(trim($cfg['ai_provider'] ?? ''));
        $this->apiKey = trim($cfg['ai_api_key'] ?? '');
        $this->model = trim($cfg['ai_model'] ?? '');
        $this->systemPrompt = trim($cfg['system_prompt'] ?? '');
        $this->baseUrl = $cfg['ai_base_url'] ?? null;
    }

    public function configured(): bool
    {
        return in_array($this->provider, ['gemini', 'openai', 'openrouter'], true)
            && $this->apiKey !== '' && $this->model !== '';
    }

    public function provider(): string { return $this->provider; }
    public function model(): string { return $this->model; }

    /**
     * Kirim percakapan ke AI.
     * @param array $history [['role'=>'user'|'assistant','content'=>'...'], ...] pesan lama
     * @return string jawaban AI
     * @throws AIException bila provider menolak / jaringan gagal / respon kosong
     */
    public function chat(array $history, string $userText): string
    {
        if (!$this->configured()) {
            throw new AIException('AI belum dikonfigurasi (provider / API key / model kosong).');
        }
        return $this->provider === 'gemini'
            ? $this->chatGemini($history, $userText)
            : $this->chatOpenAICompatible($history, $userText);
    }

    // ---------- Gemini (Google AI Studio) ----------
    private function chatGemini(array $history, string $userText): string
    {
        $base = $this->baseUrl ?: 'https://generativelanguage.googleapis.com/v1beta/models/';
        $url = rtrim($base, '/') . '/' . $this->model . ':generateContent';

        $contents = [];
        foreach ($history as $m) {
            $contents[] = [
                'role' => $m['role'] === 'assistant' ? 'model' : 'user',
                'parts' => [['text' => $m['content']]],
            ];
        }
        $contents[] = ['role' => 'user', 'parts' => [['text' => $userText]]];

        $body = ['contents' => $contents];
        if ($this->systemPrompt !== '') {
            $body['system_instruction'] = ['parts' => [['text' => $this->systemPrompt]]];
        }

        $data = $this->postJson($url, $body, ['x-goog-api-key: ' . $this->apiKey]);
        $text = $data['candidates'][0]['content']['parts'][0]['text'] ?? '';
        if (trim($text) === '') {
            throw new AIException('Gemini mengembalikan jawaban kosong.');
        }
        return trim($text);
    }

    // ---------- OpenAI & OpenRouter (format chat/completions yang sama) ----------
    private function chatOpenAICompatible(array $history, string $userText): string
    {
        $defaultBase = $this->provider === 'openrouter'
            ? 'https://openrouter.ai/api/v1'
            : 'https://api.openai.com/v1';
        $url = rtrim($this->baseUrl ?: $defaultBase, '/') . '/chat/completions';

        $messages = [];
        if ($this->systemPrompt !== '') {
            $messages[] = ['role' => 'system', 'content' => $this->systemPrompt];
        }
        foreach ($history as $m) {
            $messages[] = ['role' => $m['role'], 'content' => $m['content']];
        }
        $messages[] = ['role' => 'user', 'content' => $userText];

        $data = $this->postJson($url, [
            'model' => $this->model,
            'messages' => $messages,
        ], ['Authorization: Bearer ' . $this->apiKey]);

        $text = $data['choices'][0]['message']['content'] ?? '';
        if (trim((string)$text) === '') {
            throw new AIException('Provider AI mengembalikan jawaban kosong.');
        }
        return trim($text);
    }

    /** POST JSON + urai respon; lempar AIException berisi pesan error provider bila gagal. */
    private function postJson(string $url, array $body, array $extraHeaders): array
    {
        $ch = curl_init($url);
        curl_setopt_array($ch, [
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => json_encode($body),
            CURLOPT_HTTPHEADER => array_merge(['Content-Type: application/json'], $extraHeaders),
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT => 60,
        ]);
        $raw = curl_exec($ch);
        $err = curl_error($ch);
        $code = (int)curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
        curl_close($ch);

        if ($raw === false) {
            throw new AIException("Jaringan ke provider AI gagal: $err");
        }
        $data = json_decode($raw, true);
        if ($code >= 400 || !is_array($data)) {
            $msg = $data['error']['message'] ?? $data['error'] ?? "HTTP $code";
            throw new AIException('Provider AI menolak: ' . (is_string($msg) ? $msg : json_encode($msg)));
        }
        if (isset($data['error'])) {
            $msg = $data['error']['message'] ?? json_encode($data['error']);
            throw new AIException('Provider AI error: ' . $msg);
        }
        return $data;
    }
}
