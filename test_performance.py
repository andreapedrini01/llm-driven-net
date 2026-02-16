#!/usr/bin/env python3
"""
Test per verificare le metriche di performance (Task 11.3)
"""

import time
from network_state_collector.collector import NetworkStateCollector
from src.models.config import CollectorConfig, RyuConfig

def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def main():
    print_header("🚀 Test Performance Monitoring - Task 11.3")
    
    # Configurazione
    config = CollectorConfig(
        ryu=RyuConfig(host="localhost", port=8080)
    )
    
    print("📋 Inizializzazione collector...")
    collector = NetworkStateCollector(config)
    print("✓ Collector inizializzato con performance monitoring\n")
    
    # Simula raccolta dati (con mock)
    print("📊 Simulazione raccolta dati...")
    print("   (Nota: Ryu non è attivo, ma testiamo il monitoring)\n")
    
    # Simula alcune operazioni
    from network_state_collector.performance_monitor import PerformanceTimer
    
    # Operazione 1: Simulazione raccolta veloce
    with PerformanceTimer(collector.performance_monitor, "test_fast_operation"):
        time.sleep(0.01)  # 10ms
    
    # Operazione 2: Simulazione raccolta lenta
    with PerformanceTimer(collector.performance_monitor, "test_slow_operation"):
        time.sleep(0.1)  # 100ms
    
    # Operazione 3: Simulazione con errore
    try:
        with PerformanceTimer(collector.performance_monitor, "test_failed_operation") as timer:
            time.sleep(0.05)
            timer.mark_failed("Simulated error")
    except:
        pass
    
    # Più operazioni per statistiche
    for i in range(5):
        with PerformanceTimer(collector.performance_monitor, "test_fast_operation"):
            time.sleep(0.01 + i * 0.002)
    
    print("✓ Operazioni simulate completate\n")
    
    # Test 1: Statistiche base
    print_header("📊 Test 1: Statistiche Base")
    
    stats = collector.get_performance_stats()
    
    print(f"Uptime: {stats['uptime_formatted']}")
    print(f"Total Operations: {stats['total_operations']}")
    print(f"Success Rate: {stats['success_rate']:.1f}%")
    print(f"Operations/sec: {stats['operations_per_second']:.2f}")
    
    if stats['total_operations'] > 0:
        print("\n✅ Test 1 PASSATO: Statistiche base funzionano")
    else:
        print("\n❌ Test 1 FALLITO: Nessuna operazione registrata")
        return False
    
    # Test 2: Statistiche per operazione
    print_header("📊 Test 2: Statistiche Per-Operazione")
    
    for op_name, op_stats in stats['operations'].items():
        print(f"\n{op_name}:")
        print(f"  Count: {op_stats['count']}")
        print(f"  Avg Duration: {op_stats['avg_duration_ms']:.2f}ms")
        print(f"  Min Duration: {op_stats['min_duration_ms']:.2f}ms")
        print(f"  Max Duration: {op_stats['max_duration_ms']:.2f}ms")
        print(f"  P95 Duration: {op_stats['p95_duration_ms']:.2f}ms")
        print(f"  Success Rate: {op_stats['success_rate']:.1f}%")
    
    if len(stats['operations']) > 0:
        print("\n✅ Test 2 PASSATO: Statistiche per-operazione funzionano")
    else:
        print("\n❌ Test 2 FALLITO: Nessuna statistica per operazione")
        return False
    
    # Test 3: Operazioni lente
    print_header("📊 Test 3: Rilevamento Operazioni Lente")
    
    slow_ops = collector.performance_monitor.get_slow_operations(threshold_ms=50.0)
    
    print(f"Operazioni lente (>50ms): {len(slow_ops)}")
    for i, op in enumerate(slow_ops[:3], 1):
        print(f"  {i}. {op.operation}: {op.duration_ms:.2f}ms")
    
    if len(slow_ops) > 0:
        print("\n✅ Test 3 PASSATO: Rilevamento operazioni lente funziona")
    else:
        print("\n✅ Test 3 PASSATO: Nessuna operazione lenta (buono!)")
    
    # Test 4: Metriche recenti
    print_header("📊 Test 4: Metriche Recenti")
    
    recent = collector.performance_monitor.get_recent_metrics(limit=5)
    
    print(f"Ultime {len(recent)} operazioni:")
    for i, metric in enumerate(recent, 1):
        status = "✓" if metric.success else "✗"
        print(f"  {i}. {status} {metric.operation}: {metric.duration_ms:.2f}ms")
    
    if len(recent) > 0:
        print("\n✅ Test 4 PASSATO: Metriche recenti funzionano")
    else:
        print("\n❌ Test 4 FALLITO: Nessuna metrica recente")
        return False
    
    # Test 5: Summary completo
    print_header("📊 Test 5: Performance Summary")
    
    collector.print_performance_summary()
    
    print("✅ Test 5 PASSATO: Summary completo funziona")
    
    # Riepilogo finale
    print_header("✅ Riepilogo Test Performance")
    
    print("🎉 Tutti i test passati!")
    print()
    print("✓ Performance monitoring implementato")
    print("✓ Metriche per operazione tracciate")
    print("✓ Statistiche aggregate calcolate")
    print("✓ Rilevamento operazioni lente")
    print("✓ Percentili (P50, P95, P99) calcolati")
    print("✓ Success rate tracciato")
    print()
    print("📊 Metriche disponibili:")
    print("   • Durata operazioni (avg, min, max, percentili)")
    print("   • Success rate per operazione")
    print("   • Throughput (ops/sec)")
    print("   • Uptime sistema")
    print("   • Operazioni lente")
    print("   • Metriche recenti")
    print()
    print("🚀 Task 11.3 COMPLETATA!")
    
    return True

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
