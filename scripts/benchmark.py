#!/usr/bin/env python3
"""Prosty benchmark szybkości i zasobów Ollamy."""

import argparse
import csv
import hashlib
import json
import os
import platform
import random
import shutil
import statistics
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil
import requests


def now():
    return datetime.now(timezone.utc).isoformat()


def api(base_url, method, path, data=None, timeout=900):
    response = requests.request(
        method, base_url.rstrip("/") + path, json=data, timeout=timeout
    )
    if not response.ok:
        raise RuntimeError(response.text)
    return response.json()


def nvidia_sample():
    if not shutil.which("nvidia-smi"):
        return []
    command = [
        "nvidia-smi",
        "--query-gpu=utilization.gpu,memory.used,temperature.gpu,power.draw",
        "--format=csv,noheader,nounits",
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    samples = []
    for line in result.stdout.splitlines():
        try:
            values = [float(value.strip()) for value in line.split(",")]
            samples.append(values)
        except ValueError:
            pass
    return samples


def ollama_rss():
    total = 0
    for process in psutil.process_iter(["name", "memory_info"]):
        try:
            if "ollama" in (process.info["name"] or "").lower():
                total += process.info["memory_info"].rss
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass
    return total


class Monitor:
    def __init__(self, interval):
        self.interval = interval
        self.samples = []
        self.stop = threading.Event()

    def sample(self):
        memory = psutil.virtual_memory()
        self.samples.append(
            {
                "ram": memory.used,
                "cpu": psutil.cpu_percent(),
                "ollama_rss": ollama_rss(),
                "gpu": nvidia_sample(),
            }
        )

    def loop(self):
        while not self.stop.wait(self.interval):
            self.sample()

    def __enter__(self):
        self.sample()
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join()
        self.sample()

    def result(self):
        ram = [sample["ram"] for sample in self.samples]
        rss = [sample["ollama_rss"] for sample in self.samples]
        cpu = [sample["cpu"] for sample in self.samples]
        gpu = [row for sample in self.samples for row in sample["gpu"]]

        def gpu_values(column):
            return [row[column] for row in gpu]

        utilization = gpu_values(0)
        vram = gpu_values(1)
        temperature = gpu_values(2)
        power = gpu_values(3)
        return {
            "ram_peak_gib": max(ram) / 1024**3,
            "ram_delta_gib": (max(ram) - ram[0]) / 1024**3,
            "ollama_rss_peak_gib": max(rss) / 1024**3,
            "cpu_avg_percent": statistics.fmean(cpu),
            "gpu_avg_percent": statistics.fmean(utilization) if utilization else None,
            "gpu_peak_percent": max(utilization) if utilization else None,
            "vram_peak_mib": max(vram) if vram else None,
            "gpu_temperature_peak_c": max(temperature) if temperature else None,
            "gpu_power_avg_w": statistics.fmean(power) if power else None,
        }


def measured(function, interval):
    start = time.perf_counter()
    with Monitor(interval) as monitor:
        response = function()
    return response, time.perf_counter() - start, monitor.result()


def model_memory(base_url, model, timeout):
    loaded = api(base_url, "GET", "/api/ps", timeout=timeout).get("models", [])
    data = next(
        (item for item in loaded if model in (item.get("name"), item.get("model"))),
        {},
    )
    size = data.get("size")
    vram = data.get("size_vram")
    if not size or vram is None:
        return {}
    return {
        "model_size_gib": size / 1024**3,
        "model_vram_gib": vram / 1024**3,
        "model_ram_gib_estimate": (size - vram) / 1024**3,
        "gpu_split_percent": 100 * vram / size,
        "cpu_split_percent": 100 * (size - vram) / size,
    }


def unload_all_models(base_url, timeout):
    """Usuwa z RAM/VRAM wszystkie modele widoczne w Ollamie."""
    loaded = api(base_url, "GET", "/api/ps", timeout=timeout).get("models", [])
    for item in loaded:
        model = item.get("name") or item.get("model")
        if model:
            api(
                base_url,
                "POST",
                "/api/generate",
                {"model": model, "prompt": "", "stream": False, "keep_alive": 0},
                timeout,
            )

    deadline = time.time() + 60
    while time.time() < deadline:
        if not api(base_url, "GET", "/api/ps", timeout=timeout).get("models", []):
            return
        time.sleep(0.5)
    raise RuntimeError("Ollama did not unload all models within 60 seconds")


def save_csv(path, rows):
    if not rows:
        return
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def system_info(base_url, timeout):
    info = {
        "timestamp_utc": now(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu_logical": psutil.cpu_count(),
        "cpu_physical": psutil.cpu_count(logical=False),
        "ram_total_gib": psutil.virtual_memory().total / 1024**3,
        "ollama_environment": {
            key: value
            for key, value in os.environ.items()
            if key.startswith("OLLAMA_") and "KEY" not in key
        },
    }
    if shutil.which("nvidia-smi"):
        info["nvidia_smi"] = subprocess.run(
            ["nvidia-smi"], capture_output=True, text=True, timeout=20
        ).stdout
    info["ollama_version"] = api(
        base_url, "GET", "/api/version", timeout=timeout
    ).get("version")
    info["ollama_models"] = api(
        base_url, "GET", "/api/tags", timeout=timeout
    ).get("models", [])
    return info


def generation_request(config, model, prompt, num_predict):
    return api(
        config["api_url"],
        "POST",
        "/api/generate",
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": config["keep_alive"],
            "options": {
                "num_predict": num_predict,
                "num_ctx": config["num_ctx"],
                "temperature": config["temperature"],
                "seed": config["seed"],
            },
        },
        config["request_timeout_seconds"],
    )


def summary(results):
    groups = {}
    for row in results:
        if row["status"] == "success":
            groups.setdefault((row["model"], row["profile"]), []).append(row)
    output = []
    for (model, profile), rows in sorted(groups.items()):
        generation = [row["generation_tokens_per_second"] for row in rows]
        prompt = [row["prompt_tokens_per_second"] for row in rows]
        output.append(
            {
                "model": model,
                "profile": profile,
                "requests": len(rows),
                "generation_tokens_per_second_mean": statistics.fmean(generation),
                "generation_tokens_per_second_median": statistics.median(generation),
                "prompt_tokens_per_second_mean": statistics.fmean(prompt),
                "prompt_tokens_per_second_median": statistics.median(prompt),
            }
        )
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config/benchmark.json"))
    parser.add_argument("--models", nargs="+")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    root = args.config.resolve().parent.parent
    prompts_document = json.loads(
        (root / config["prompts_file"]).read_text(encoding="utf-8")
    )
    prompts = prompts_document["prompts"][: args.limit]
    models = args.models or config["models"]
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = args.output_dir or root / "results" / run_id
    output_dir.mkdir(parents=True)

    run_config = {
        **config,
        "models": models,
        "prompt_count_used": len(prompts),
        "prompt_source": prompts_document["source"],
        "prompts_sha256": hashlib.sha256(
            json.dumps(prompts, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest(),
    }
    save_json(output_dir / "run_config.json", run_config)
    save_json(
        output_dir / "system_info.json",
        system_info(config["api_url"], config["request_timeout_seconds"]),
    )

    results = []
    model_results = []
    for model in models:
        print(f"\n=== {model} ===", flush=True)
        model_row = {"model": model, "status": "running"}
        try:
            unload_all_models(config["api_url"], config["request_timeout_seconds"])
            details = api(
                config["api_url"],
                "POST",
                "/api/show",
                {"model": model, "verbose": False},
                config["request_timeout_seconds"],
            ).get("details", {})
            model_row.update(
                {
                    "parameter_size": details.get("parameter_size"),
                    "quantization": details.get("quantization_level"),
                    "format": details.get("format"),
                }
            )
            load, load_wall, load_resources = measured(
                lambda: generation_request(config, model, prompts[0]["text"], 1),
                config["sample_interval_seconds"],
            )
            model_row["cold_load_ms"] = load.get("load_duration", 0) / 1_000_000
            model_row["cold_load_wall_seconds"] = load_wall
            model_row.update(model_memory(config["api_url"], model, config["request_timeout_seconds"]))
            model_row.update({f"cold_{key}": value for key, value in load_resources.items()})

            for _ in range(config["warmup_requests"]):
                generation_request(config, model, prompts[0]["text"], 32)

            out_of_memory = False
            for repetition in range(1, config["repetitions"] + 1):
                order = list(prompts)
                random.Random(config["seed"] + repetition).shuffle(order)
                for number, prompt in enumerate(order, 1):
                    base = {
                        "timestamp_utc": now(),
                        "model": model,
                        "profile": prompt["profile"],
                        "prompt_id": prompt["id"],
                        "prompt_chars": len(prompt["text"]),
                        "repetition": repetition,
                        "position": number,
                        "cold_load_ms": model_row["cold_load_ms"],
                        **model_memory(
                            config["api_url"], model, config["request_timeout_seconds"]
                        ),
                    }
                    try:
                        response, wall_time, resources = measured(
                            lambda: generation_request(
                                config, model, prompt["text"], config["num_predict"]
                            ),
                            config["sample_interval_seconds"],
                        )
                        prompt_seconds = response["prompt_eval_duration"] / 1_000_000_000
                        generation_seconds = response["eval_duration"] / 1_000_000_000
                        row = {
                            **base,
                            "status": "success",
                            "wall_time_seconds": wall_time,
                            "load_ms": response.get("load_duration", 0) / 1_000_000,
                            "prompt_tokens": response["prompt_eval_count"],
                            "prompt_tokens_per_second": response["prompt_eval_count"]
                            / prompt_seconds,
                            "output_tokens": response["eval_count"],
                            "generation_tokens_per_second": response["eval_count"]
                            / generation_seconds,
                            "done_reason": response.get("done_reason"),
                            **resources,
                        }
                    except Exception as error:
                        message = str(error)
                        out_of_memory = "out of memory" in message.lower() or "oom" in message.lower()
                        row = {
                            **base,
                            "status": "oom" if out_of_memory else "error",
                            "error": message,
                        }
                    results.append(row)
                    save_json(output_dir / "results.json", results)
                    save_csv(output_dir / "results.csv", results)
                    print(
                        f"[{repetition}/{config['repetitions']}] {number}/{len(order)} "
                        f"{prompt['profile']}: {row['status']}",
                        flush=True,
                    )
                    if out_of_memory:
                        break
                if out_of_memory:
                    break
            model_row["status"] = "oom" if out_of_memory else "success"
        except Exception as error:
            model_row["status"] = "oom" if "memory" in str(error).lower() else "error"
            model_row["error"] = str(error)
        finally:
            try:
                unload_all_models(config["api_url"], config["request_timeout_seconds"])
            except Exception as error:
                model_row["cleanup_error"] = str(error)
        model_results.append(model_row)
        save_json(output_dir / "models.json", model_results)
        save_csv(output_dir / "models.csv", model_results)

    summary_rows = summary(results)
    save_json(output_dir / "summary.json", summary_rows)
    save_csv(output_dir / "summary.csv", summary_rows)
    print(f"\nWyniki: {output_dir}")


if __name__ == "__main__":
    main()
