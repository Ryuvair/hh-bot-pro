import asyncio
from mtprotoproxy import MTProtoProxy

async def main():
    proxy = MTProtoProxy(
        host="130.49.5.41",
        port=443,
        secret=bytes.fromhex("ee3196a49fcbc0b8767ca723c875c815d779612e7275"),
        local_host="127.0.0.1",
        local_port=1080
    )
    print("🚀 Туннель запущен на 127.0.0.1:1080")
    await proxy.start()

if __name__ == "__main__":
    asyncio.run(main())