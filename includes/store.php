<?php
// Penyimpanan riwayat percakapan per chat — satu file JSON per chat_id
// di folder data/. Cukup untuk bot pribadi/skala kecil; untuk trafik besar
// ganti implementasi class ini dengan database (SQLite/MySQL), API-nya sama.
class ChatStore
{
    private string $dir;
    private int $limit;

    public function __construct(string $dir, int $limit = 20)
    {
        $this->dir = rtrim($dir, '/');
        $this->limit = max(2, $limit);
        if (!is_dir($this->dir)) {
            mkdir($this->dir, 0775, true);
        }
    }

    private function path(int|string $chatId): string
    {
        // chat_id Telegram berupa angka (boleh negatif untuk grup)
        $safe = preg_replace('/[^0-9\-]/', '', (string)$chatId);
        return $this->dir . '/chat_' . $safe . '.json';
    }

    /** @return array [['role'=>'user'|'assistant','content'=>'...'], ...] */
    public function get(int|string $chatId): array
    {
        $f = $this->path($chatId);
        if (!is_file($f)) {
            return [];
        }
        $data = json_decode((string)file_get_contents($f), true);
        return is_array($data) ? $data : [];
    }

    public function append(int|string $chatId, string $role, string $content): void
    {
        $hist = $this->get($chatId);
        $hist[] = ['role' => $role, 'content' => $content];
        if (count($hist) > $this->limit) {
            $hist = array_slice($hist, -$this->limit);
        }
        file_put_contents(
            $this->path($chatId),
            json_encode($hist, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT),
            LOCK_EX
        );
    }

    public function clear(int|string $chatId): void
    {
        $f = $this->path($chatId);
        if (is_file($f)) {
            unlink($f);
        }
    }
}
