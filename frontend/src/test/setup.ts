import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

// localStorage를 메모리 스텁으로 고정한다. Node 25+는 자체 전역 `localStorage`(webstorage)를
// 노출하는데 `--localstorage-file` 없이는 메서드가 없는 객체라, jsdom 것 대신 그것이 잡혀
// `localStorage.clear()`가 TypeError로 죽는다. Node 버전·플래그와 무관하게 같은 동작을 보장한다.
class MemoryStorage implements Storage {
  private data = new Map<string, string>();
  get length(): number {
    return this.data.size;
  }
  clear(): void {
    this.data.clear();
  }
  getItem(key: string): string | null {
    return this.data.get(String(key)) ?? null;
  }
  key(index: number): string | null {
    return [...this.data.keys()][index] ?? null;
  }
  removeItem(key: string): void {
    this.data.delete(String(key));
  }
  setItem(key: string, value: string): void {
    this.data.set(String(key), String(value));
  }
}

const memoryStorage = new MemoryStorage();
for (const target of [globalThis, window]) {
  Object.defineProperty(target, "localStorage", {
    value: memoryStorage,
    configurable: true,
    writable: true,
  });
}

afterEach(() => {
  cleanup();
  memoryStorage.clear();
});
