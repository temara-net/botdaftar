<?php
// Klien Telegram Bot API — hanya memakai cURL, tanpa library luar.
class TelegramBot
{
    private string $apiBase;

    public function __construct(string $token, ?string $apiBase = null)
    {
        $this->apiBase = $apiBase ?: ("https://api.telegram.org/bot" . $token . "/");
    }

    /** Panggil method Bot API apa pun. Mengembalikan array hasil / null bila gagal jaringan. */
    public function call(string $method, array $params = []): ?array
    {
        $ch = curl_init($this->apiBase . $method);
        curl_setopt_array($ch, [
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => json_encode($params),
            CURLOPT_HTTPHEADER => ['Content-Type: application/json'],
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT => 30,
        ]);
        $raw = curl_exec($ch);
        $err = curl_error($ch);
        curl_close($ch);
        if ($raw === false) {
            error_log("[telegram] curl error $method: $err");
            return null;
        }
        $data = json_decode($raw, true);
        if (!is_array($data)) {
            error_log("[telegram] respon bukan JSON pada $method");
            return null;
        }
        if (empty($data['ok'])) {
            error_log("[telegram] $method ditolak: " . ($data['description'] ?? $raw));
        }
        return $data;
    }

    /** Kirim pesan teks; pesan panjang otomatis dipecah per 4096 karakter (batas Telegram). */
    public function sendMessage(int|string $chatId, string $text): ?array
    {
        $last = null;
        foreach ($this->split($text) as $chunk) {
            $last = $this->call('sendMessage', [
                'chat_id' => $chatId,
                'text' => $chunk,
            ]);
        }
        return $last;
    }

    /** Indikator "sedang mengetik..." */
    public function sendTyping(int|string $chatId): void
    {
        $this->call('sendChatAction', ['chat_id' => $chatId, 'action' => 'typing']);
    }

    /** Pecah teks di batas baris/spasi sedekat mungkin dengan batas Telegram. */
    public function split(string $text, int $limit = 4096): array
    {
        if (mb_strlen($text) <= $limit) {
            return [$text];
        }
        $chunks = [];
        $rest = $text;
        while (mb_strlen($rest) > $limit) {
            $cut = mb_strrpos(mb_substr($rest, 0, $limit), "\n");
            if ($cut === false || $cut < 200) {
                $cut = mb_strrpos(mb_substr($rest, 0, $limit), ' ');
            }
            if ($cut === false || $cut < 200) {
                $cut = $limit;
            }
            $chunks[] = trim(mb_substr($rest, 0, $cut));
            $rest = trim(mb_substr($rest, $cut));
        }
        if ($rest !== '') {
            $chunks[] = $rest;
        }
        return $chunks;
    }
}
