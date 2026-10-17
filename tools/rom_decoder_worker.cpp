// Optional offline scanner helper. Link with a separately obtained local
// Kraken decoder; keep that dependency and all generated outputs in work/.
// Protocol: little-endian u64 input/output sizes, compressed bytes; reply with
// i64 decoded size and bytes on success. Intended host: little-endian macOS.
#include <cstdint>
#include <cstdio>
#include <vector>
#include <sys/types.h>
extern "C" ssize_t Kraken_Decompress(const uint8_t *, size_t, uint8_t *, size_t);

int main() {
    uint64_t sizes[2];
    for (;;) {
        size_t header = fread(sizes, 1, sizeof sizes, stdin);
        if (!header) return 0;
        if (header != sizeof sizes) return 2;
        if (sizes[0] > 512 * 1024 * 1024 || sizes[1] > 512 * 1024 * 1024) return 3;
        // Decoder documentation requires 64 bytes of readable/writable slack.
        std::vector<uint8_t> input(sizes[0] + 64), output(sizes[1] + 64);
        if (fread(input.data(), 1, sizes[0], stdin) != sizes[0]) return 4;
        int64_t count = Kraken_Decompress(input.data(), sizes[0], output.data(), sizes[1]);
        if (fwrite(&count, 1, sizeof count, stdout) != sizeof count) return 5;
        if (count == static_cast<int64_t>(sizes[1]) &&
            fwrite(output.data(), 1, count, stdout) != static_cast<size_t>(count)) return 6;
        if (fflush(stdout)) return 7;
    }
}
