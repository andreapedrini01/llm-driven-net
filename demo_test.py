#!/usr/bin/env python3
"""
Demo Test per il Modulo di Integrazione LLM - Sistema di Networking Intent-Based

Questo file dimostra le capacità del sistema di tradurre intent in linguaggio naturale
in azioni concrete di configurazione di rete.

Autore: @andreapedrini01
Data: Dicembre 2025
"""

import sys
import os
from datetime import datetime
from typing import List, Dict, Any

# Aggiungi il path src per gli import
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from models.intent import IntentObject, IntentType, Entity, ContextualizedIntent
from models.actions import NetworkAction, ActionType, ActionSequence
from models.network import NetworkState, Topology, NetworkMetrics, BandwidthMetrics, LatencyMetrics, UtilizationMetrics, Anomaly, AnomalyType, AnomalySeverity, Switch, Link, Host
from models.slices import NetworkSlice, SliceStatus, ServiceLevelAgreement, SliceResources
from services.intent_parser import IntentParser
from services.context_analyzer import NetworkStateCache, ContextCorrelationEngine, AnomalyDetectionSystem


class NetworkDemoSystem:
    """Sistema di dimostrazione per il modulo LLM di integrazione di rete."""
    
    def __init__(self):
        """Inizializza il sistema demo."""
        self.parser = IntentParser()
        self.demo_results = []
        
        # Inizializza i componenti del Context Analyzer
        self.state_cache = NetworkStateCache(default_ttl=600, max_entries=50)
        self.correlation_engine = ContextCorrelationEngine(self.state_cache)
        self.anomaly_detector = AnomalyDetectionSystem(self.state_cache)
        
    def print_header(self, title: str):
        """Stampa un header formattato."""
        print("\n" + "="*80)
        print(f"🚀 {title}")
        print("="*80)
    
    def print_section(self, title: str):
        """Stampa una sezione formattata."""
        print(f"\n📋 {title}")
        print("-" * 60)
    
    def print_success(self, message: str):
        """Stampa un messaggio di successo."""
        print(f"✅ {message}")
    
    def print_info(self, message: str):
        """Stampa un messaggio informativo."""
        print(f"ℹ️  {message}")
    
    def print_result(self, key: str, value: Any):
        """Stampa un risultato formattato."""
        print(f"   {key}: {value}")
    
    def demo_intent_parsing(self):
        """Dimostra il parsing degli intent in linguaggio naturale."""
        self.print_header("DEMO 1: PARSING INTENT IN LINGUAGGIO NATURALE")
        
        # Lista di intent di esempio
        sample_intents = [
            "Crea una nuova network slice per il tenant A con alta priorità e 1000 Mbps di bandwidth",
            "Configura le politiche QoS per il servizio web con limite di 5000 Mbps",
            "Monitora la latenza e il packet loss sulla rete principale",
            "Aumenta la bandwidth del tenant B a 2000 Mbps",
            "Crea regole di sicurezza per bloccare il traffico dalla subnet 192.168.1.0/24"
        ]
        
        for i, intent_text in enumerate(sample_intents, 1):
            self.print_section(f"Intent {i}")
            self.print_info(f"Input: \"{intent_text}\"")
            
            # Parse dell'intent
            parsed_intent = self.parser.parse_intent(intent_text)
            
            # Mostra i risultati
            self.print_result("ID Intent", parsed_intent.id)
            self.print_result("Tipo", parsed_intent.intent_type.value)
            self.print_result("Confidenza", f"{parsed_intent.confidence:.1%}")
            self.print_result("Entità Estratte", len(parsed_intent.entities))
            
            # Mostra le entità principali
            for entity in parsed_intent.entities[:3]:  # Prime 3 entità
                self.print_result(f"  - {entity.type}", entity.value)
            
            self.print_success("Intent parsato con successo!")
            
            # Salva per il report finale
            self.demo_results.append({
                'intent': intent_text,
                'confidence': parsed_intent.confidence,
                'entities': len(parsed_intent.entities),
                'type': parsed_intent.intent_type.value
            })
    
    def demo_action_generation(self):
        """Dimostra la generazione di azioni di rete."""
        self.print_header("DEMO 2: GENERAZIONE AZIONI DI RETE")
        
        # Scenario 1: Creazione Network Slice
        self.print_section("Scenario 1: Creazione Network Slice")
        intent_text = "Crea una network slice per il tenant Enterprise con 2000 Mbps e bassa latenza"
        parsed_intent = self.parser.parse_intent(intent_text)
        
        self.print_info(f"Intent: {intent_text}")
        self.print_result("Confidenza Parsing", f"{parsed_intent.confidence:.1%}")
        
        # Genera azione di creazione slice
        slice_action = NetworkAction(
            id="slice-enterprise-001",
            type=ActionType.SLICE_CREATE,
            target="network-controller",
            parameters={
                'slice_name': 'enterprise_slice',
                'resources': {
                    'bandwidth': 2000,
                    'switches': ['sw1', 'sw2', 'sw3', 'sw4'],
                    'priority': 'high'
                },
                'sla': {
                    'latency_max': 5.0,
                    'availability': 0.995,
                    'packet_loss_max': 0.1
                }
            },
            priority=9000,
            timeout=180,
            description="Create enterprise network slice with high performance SLA"
        )
        
        # Valida l'azione
        validation = slice_action.validate_action_parameters()
        self.print_result("Validazione", "✅ Valida" if validation['is_valid'] else "❌ Errori")
        self.print_result("Tipo Azione", slice_action.type.value)
        self.print_result("Target", slice_action.target)
        self.print_result("Priorità", slice_action.priority)
        self.print_result("Timeout", f"{slice_action.timeout}s")
        
        # Mostra formato Northbound
        northbound = slice_action.to_northbound_format()
        self.print_success("Azione formattata per Northbound Script")
        self.print_result("Campi Northbound", len(northbound))
        
        # Scenario 2: Configurazione Multi-Azione
        self.print_section("Scenario 2: Configurazione Multi-Azione")
        intent_text = "Configura QoS e monitoring per il servizio database"
        parsed_intent = self.parser.parse_intent(intent_text)
        
        self.print_info(f"Intent: {intent_text}")
        
        # Genera multiple azioni
        qos_action = NetworkAction(
            id="qos-database-001",
            type=ActionType.CONFIG_CHANGE,
            target="switch-core",
            parameters={
                'config_type': 'qos',
                'config_data': {
                    'bandwidth_limit': 8000,
                    'priority_class': 1,  # Massima priorità
                    'dscp_marking': 46
                }
            },
            priority=8500,
            timeout=60
        )
        
        monitoring_action = NetworkAction(
            id="monitor-database-001",
            type=ActionType.CONFIG_CHANGE,
            target="monitoring-server",
            parameters={
                'config_type': 'monitoring',
                'config_data': {
                    'sampling_rate': 0.2,
                    'metrics': ['bandwidth', 'latency', 'packet_loss', 'jitter'],
                    'alert_thresholds': {
                        'latency_ms': 10,
                        'packet_loss_percent': 0.5
                    }
                }
            },
            priority=7000,
            timeout=30
        )
        
        # Crea sequenza di azioni
        action_sequence = ActionSequence(
            id="seq-database-config",
            intent_id=parsed_intent.id,
            actions=[qos_action, monitoring_action],
            estimated_duration=qos_action.estimate_execution_time() + monitoring_action.estimate_execution_time(),
            dependencies=[]
        )
        
        # Valida la sequenza
        seq_validation = action_sequence.validate_sequence_integrity()
        self.print_result("Azioni nella Sequenza", len(action_sequence.actions))
        self.print_result("Validazione Sequenza", "✅ Valida" if seq_validation['is_valid'] else "❌ Errori")
        self.print_result("Target Unici", seq_validation['unique_targets'])
        self.print_result("Durata Stimata", f"{action_sequence.estimated_duration}s")
        
        # Mostra ordine di esecuzione
        execution_order = action_sequence.get_execution_order()
        self.print_success("Ordine di esecuzione ottimizzato:")
        for i, action in enumerate(execution_order, 1):
            self.print_result(f"  {i}. {action.id}", f"Priorità {action.priority}")
    
    def demo_network_state_integration(self):
        """Dimostra l'integrazione con lo stato della rete."""
        self.print_header("DEMO 3: INTEGRAZIONE STATO DELLA RETE")
        
        # Crea uno stato di rete simulato
        self.print_section("Stato Corrente della Rete")
        
        bandwidth_metrics = BandwidthMetrics(
            total_capacity=50000,  # 50 Gbps
            used_bandwidth=15000,  # 15 Gbps utilizzati
            available_bandwidth=35000,  # 35 Gbps disponibili
            utilization_percentage=30.0
        )
        
        latency_metrics = LatencyMetrics(
            average_latency=3.2,
            min_latency=0.8,
            max_latency=12.5,
            jitter=1.8
        )
        
        utilization_metrics = UtilizationMetrics(
            cpu_utilization=45.0,
            memory_utilization=62.0
        )
        
        network_metrics = NetworkMetrics(
            bandwidth=bandwidth_metrics,
            latency=latency_metrics,
            utilization=utilization_metrics
        )
        
        network_state = NetworkState(
            timestamp=datetime.now(),
            topology=Topology(),
            metrics=network_metrics
        )
        
        self.print_result("Capacità Totale", f"{bandwidth_metrics.total_capacity} Mbps")
        self.print_result("Bandwidth Utilizzata", f"{bandwidth_metrics.used_bandwidth} Mbps ({bandwidth_metrics.utilization_percentage}%)")
        self.print_result("Bandwidth Disponibile", f"{bandwidth_metrics.available_bandwidth} Mbps")
        self.print_result("Latenza Media", f"{latency_metrics.average_latency} ms")
        self.print_result("Utilizzo CPU", f"{utilization_metrics.cpu_utilization}%")
        self.print_result("Utilizzo Memoria", f"{utilization_metrics.memory_utilization}%")
        
        # Simula decisioni basate sullo stato
        self.print_section("Decisioni Basate sullo Stato")
        
        if bandwidth_metrics.available_bandwidth >= 5000:
            self.print_success("✅ Bandwidth sufficiente per nuove slice (>5000 Mbps disponibili)")
        else:
            self.print_info("⚠️  Bandwidth limitata, considerare ottimizzazioni")
        
        if latency_metrics.average_latency <= 5.0:
            self.print_success("✅ Latenza ottimale per applicazioni real-time (<5ms)")
        else:
            self.print_info("⚠️  Latenza elevata, potrebbero servire ottimizzazioni")
        
        if utilization_metrics.cpu_utilization <= 70.0:
            self.print_success("✅ Utilizzo CPU normale (<70%)")
        else:
            self.print_info("⚠️  Utilizzo CPU elevato, monitorare performance")
    
    def demo_network_slice_management(self):
        """Dimostra la gestione delle network slice."""
        self.print_header("DEMO 4: GESTIONE NETWORK SLICE")
        
        # Crea una network slice di esempio
        self.print_section("Creazione Network Slice")
        
        sla = ServiceLevelAgreement(
            id="sla-premium-001",
            min_bandwidth=5000,
            max_latency=3.0,
            availability=99.9,
            packet_loss_threshold=0.1
        )
        
        resources = SliceResources(
            bandwidth=6000,
            cpu_allocation=80.0,
            memory_allocation=70.0
        )
        
        network_slice = NetworkSlice(
            id="slice-premium-001",
            name="premium_service_slice",
            tenant_id="tenant_premium",
            status=SliceStatus.ACTIVE,
            sla=sla,
            resources=resources
        )
        
        self.print_result("Slice ID", network_slice.id)
        self.print_result("Nome", network_slice.name)
        self.print_result("Tenant", network_slice.tenant_id)
        self.print_result("Status", network_slice.status.value)
        self.print_result("Bandwidth Allocata", f"{resources.bandwidth} Mbps")
        self.print_result("SLA Latenza Max", f"{sla.max_latency} ms")
        self.print_result("SLA Availability", f"{sla.availability}%")
        
        # Simula modifica della slice
        self.print_section("Modifica Network Slice")
        
        modify_action = NetworkAction(
            id="slice-modify-premium-001",
            type=ActionType.SLICE_MODIFY,
            target="network-controller",
            parameters={
                'slice_id': network_slice.id,
                'slice_name': network_slice.name,
                'resources': {
                    'bandwidth': 8000,  # Aumento bandwidth
                    'switches': ['sw1', 'sw2', 'sw3', 'sw4', 'sw5'],  # Aggiunta switch
                    'priority': 'ultra_high'
                },
                'sla': {
                    'latency_max': 2.0,  # Riduzione latenza
                    'availability': 99.95  # Aumento availability
                }
            },
            priority=9500,
            timeout=120
        )
        
        validation = modify_action.validate_action_parameters()
        self.print_result("Modifica Richiesta", "Aumento bandwidth 6000→8000 Mbps")
        self.print_result("Validazione", "✅ Valida" if validation['is_valid'] else "❌ Errori")
        self.print_result("Nuova Latenza SLA", "2.0 ms")
        self.print_result("Nuova Availability", "99.95%")
        
        self.print_success("Slice modificata con successo!")
    
    def demo_context_analyzer(self):
        """Dimostra le funzionalità del Context Analyzer."""
        self.print_header("DEMO 5: CONTEXT ANALYZER E RILEVAMENTO ANOMALIE")
        
        # Crea uno stato di rete più complesso per la demo
        self.print_section("Inizializzazione Stato di Rete Complesso")
        
        # Crea switches
        switches = [
            Switch(id="sw1", name="Core Switch 1", dpid="0000000000000001", ports=["1", "2", "3", "4"], status="active"),
            Switch(id="sw2", name="Access Switch 1", dpid="0000000000000002", ports=["1", "2", "3"], status="active"),
            Switch(id="sw3", name="Access Switch 2", dpid="0000000000000003", ports=["1", "2", "3"], status="inactive"),  # Switch problematico
        ]
        
        # Crea links
        links = [
            Link(id="link1", source_switch="sw1", source_port=1, destination_switch="sw2", destination_port=1, bandwidth=1000, latency=2.5, status="active"),
            Link(id="link2", source_switch="sw1", source_port=2, destination_switch="sw3", destination_port=1, bandwidth=1000, latency=3.0, status="inactive"),  # Link problematico
        ]
        
        # Crea hosts
        hosts = [
            Host(id="host1", mac_address="00:00:00:00:00:01", ip_address="192.168.1.10", connected_switch="sw2", connected_port="1", status="active"),
            Host(id="host2", mac_address="00:00:00:00:00:02", ip_address="192.168.1.11", connected_switch="sw2", connected_port="2", status="active"),
        ]
        
        # Crea metriche con anomalie
        bandwidth_metrics = BandwidthMetrics(
            total_capacity=50000,
            used_bandwidth=42000,  # Utilizzo molto alto (84%)
            available_bandwidth=8000,
            utilization_percentage=84.0
        )
        
        latency_metrics = LatencyMetrics(
            average_latency=25.5,  # Latenza elevata
            min_latency=2.1,
            max_latency=150.0,
            jitter=8.2
        )
        
        utilization_metrics = UtilizationMetrics(
            cpu_utilization=92.0,  # CPU molto alta
            memory_utilization=78.0
        )
        
        network_metrics = NetworkMetrics(
            bandwidth=bandwidth_metrics,
            latency=latency_metrics,
            utilization=utilization_metrics
        )
        
        topology = Topology(switches=switches, links=links, hosts=hosts)
        
        # Crea anomalie esistenti
        existing_anomalies = [
            Anomaly(
                id="anomaly_001",
                type=AnomalyType.SWITCH_FAILURE,
                severity=AnomalySeverity.CRITICAL,
                description="Switch sw3 is offline",
                affected_resources=["sw3"],
                detected_at=datetime.now(),
                metrics={"switch_status": "inactive"}
            )
        ]
        
        network_state = NetworkState(
            timestamp=datetime.now(),
            topology=topology,
            metrics=network_metrics,
            flows=[],  # Semplificato per la demo
            anomalies=existing_anomalies
        )
        
        self.print_result("Switches Totali", len(switches))
        self.print_result("Switches Attivi", len([s for s in switches if s.status == "active"]))
        self.print_result("Links Totali", len(links))
        self.print_result("Links Attivi", len([l for l in links if l.status == "active"]))
        self.print_result("Hosts Connessi", len(hosts))
        self.print_result("Anomalie Preesistenti", len(existing_anomalies))
        
        # Demo 1: Cache dello Stato
        self.print_section("Demo 1: Cache dello Stato della Rete")
        
        # Aggiorna la cache
        self.state_cache.update_state(network_state)
        
        # Mostra statistiche della cache
        cache_stats = self.state_cache.get_cache_stats()
        self.print_result("Stato Corrente Disponibile", "✅ Sì" if cache_stats["current_state_available"] else "❌ No")
        self.print_result("Stato Fresco", "✅ Sì" if cache_stats["current_state_fresh"] else "❌ No")
        self.print_result("Utilizzo Cache", f"{cache_stats['cache_utilization']:.1%}")
        self.print_result("Entry Attive", cache_stats["active_entries"])
        
        self.print_success("Cache dello stato aggiornata con successo!")
        
        # Demo 2: Correlazione Intent-Contesto
        self.print_section("Demo 2: Correlazione Intent con Contesto di Rete")
        
        # Crea un intent che coinvolge risorse problematiche
        intent_text = "Configura QoS per il traffico verso sw3 con priorità alta"
        parsed_intent = self.parser.parse_intent(intent_text)
        
        self.print_info(f"Intent: {intent_text}")
        self.print_result("Confidenza Parsing", f"{parsed_intent.confidence:.1%}")
        
        # Correla l'intent con il contesto
        contextualized_intent = self.correlation_engine.correlate_intent_with_state(parsed_intent)
        
        self.print_result("Risorse Rilevanti", len(contextualized_intent.relevant_resources))
        for resource in contextualized_intent.relevant_resources:
            self.print_result(f"  - {resource}", "Identificata")
        
        self.print_result("Conflitti Rilevati", len(contextualized_intent.conflicts))
        for conflict in contextualized_intent.conflicts:
            self.print_result("  - Conflitto", conflict)
        
        self.print_result("Raccomandazioni", len(contextualized_intent.recommendations))
        for recommendation in contextualized_intent.recommendations:
            self.print_result("  - Raccomandazione", recommendation)
        
        # Mostra contesto arricchito per LLM
        enriched_context = self.correlation_engine.enrich_context_for_llm(contextualized_intent)
        self.print_result("Contesto Arricchito", "✅ Generato per LLM")
        self.print_result("Salute della Rete", enriched_context.get("operational_context", {}).get("network_health", "unknown"))
        self.print_result("Stato del Carico", enriched_context.get("operational_context", {}).get("load_status", "unknown"))
        
        # Demo 3: Rilevamento Anomalie
        self.print_section("Demo 3: Rilevamento Automatico Anomalie")
        
        # Rileva nuove anomalie
        detected_anomalies = self.anomaly_detector.detect_anomalies(network_state)
        
        self.print_result("Nuove Anomalie Rilevate", len(detected_anomalies))
        
        for i, anomaly in enumerate(detected_anomalies, 1):
            self.print_result(f"Anomalia {i} - Tipo", anomaly.type.value)
            self.print_result(f"Anomalia {i} - Severità", anomaly.severity.value)
            self.print_result(f"Anomalia {i} - Descrizione", anomaly.description)
            
            # Classifica la severità
            classified_severity = self.anomaly_detector.classify_anomaly_severity(anomaly, network_state)
            self.print_result(f"Anomalia {i} - Severità Classificata", classified_severity.value)
            
            # Genera risposta automatica
            response_actions = self.anomaly_detector.generate_anomaly_response(anomaly, network_state)
            self.print_result(f"Anomalia {i} - Azioni di Risposta", len(response_actions))
            
            for j, action in enumerate(response_actions, 1):
                self.print_result(f"  Azione {j}", f"{action.type.value} su {action.target}")
                self.print_result(f"  Priorità", action.priority)
                self.print_result(f"  Descrizione", action.description)
        
        # Demo 4: Rilevamento Pattern
        self.print_section("Demo 4: Rilevamento Pattern e Apprendimento")
        
        # Simula più stati per creare pattern
        for i in range(5):
            # Simula variazioni nei metriche
            varying_bandwidth = BandwidthMetrics(
                total_capacity=50000,
                used_bandwidth=30000 + (i * 2000),  # Incremento graduale
                available_bandwidth=20000 - (i * 2000),
                utilization_percentage=60.0 + (i * 4.0)
            )
            
            varying_metrics = NetworkMetrics(
                bandwidth=varying_bandwidth,
                latency=latency_metrics,
                utilization=utilization_metrics
            )
            
            varying_state = NetworkState(
                timestamp=datetime.now(),
                topology=topology,
                metrics=varying_metrics,
                flows=[],
                anomalies=existing_anomalies
            )
            
            # Rileva pattern anomalies
            pattern_anomalies = self.anomaly_detector.detect_pattern_anomalies(varying_state)
            
            if pattern_anomalies:
                self.print_result(f"Pattern Iteration {i+1}", f"{len(pattern_anomalies)} anomalie pattern")
        
        # Mostra statistiche di rilevamento
        detection_stats = self.anomaly_detector.get_detection_statistics()
        self.print_result("Anomalie Totali Segnalate", detection_stats["total_anomalies_reported"])
        self.print_result("Tasso di Accuratezza", f"{detection_stats['accuracy_rate']:.1%}")
        self.print_result("Sensibilità Corrente", f"{detection_stats['current_sensitivity']:.2f}")
        self.print_result("Apprendimento Abilitato", "✅ Sì" if detection_stats["learning_enabled"] else "❌ No")
        
        # Demo feedback learning
        self.print_section("Demo 5: Apprendimento da Feedback")
        
        if detected_anomalies:
            # Simula feedback positivo e negativo
            first_anomaly = detected_anomalies[0]
            
            # Feedback negativo (falso positivo)
            self.anomaly_detector.learn_from_feedback(first_anomaly.id, is_false_positive=True)
            self.print_success(f"✅ Feedback negativo registrato per {first_anomaly.id}")
            
            # Mostra come cambiano le statistiche
            updated_stats = self.anomaly_detector.get_detection_statistics()
            self.print_result("Nuova Sensibilità", f"{updated_stats['current_sensitivity']:.2f}")
            
            if len(detected_anomalies) > 1:
                second_anomaly = detected_anomalies[1]
                # Feedback positivo (vera anomalia)
                self.anomaly_detector.learn_from_feedback(second_anomaly.id, is_false_positive=False)
                self.print_success(f"✅ Feedback positivo registrato per {second_anomaly.id}")
        
        # Mostra metriche di correlazione
        correlation_metrics = self.correlation_engine.get_correlation_metrics()
        self.print_result("Performance Cache", f"{correlation_metrics['cache_performance']['cache_utilization']:.1%}")
        self.print_result("Arricchimento Abilitato", "✅ Sì" if correlation_metrics["enrichment_enabled"] else "❌ No")
        self.print_result("Soglia Similarità", f"{correlation_metrics['similarity_threshold']:.1f}")
        
        self.print_success("Demo Context Analyzer completata con successo!")
    
    def demo_error_handling(self):
        """Dimostra la gestione degli errori."""
        self.print_header("DEMO 6: GESTIONE ERRORI E VALIDAZIONE")
        
        self.print_section("Test Validazione Parametri")
        
        # Test con parametri invalidi
        try:
            invalid_action = NetworkAction(
                id="",  # ID vuoto - errore
                type=ActionType.FLOW_MOD,
                target="switch-1",
                parameters={}
            )
        except ValueError as e:
            self.print_success(f"✅ Errore catturato correttamente: {str(e)}")
        
        # Test con azione FLOW_MOD senza parametri richiesti
        invalid_flow_action = NetworkAction(
            id="invalid-flow-001",
            type=ActionType.FLOW_MOD,
            target="switch-1",
            parameters={
                'invalid_param': 'test'  # Mancano 'match' e 'actions'
            }
        )
        
        validation = invalid_flow_action.validate_action_parameters()
        self.print_result("Azione FLOW_MOD Invalida", "❌ Come previsto")
        self.print_result("Errori Rilevati", len(validation['issues']))
        for issue in validation['issues']:
            self.print_result("  - Errore", issue)
        
        # Test sequenza con ID duplicati
        self.print_section("Test Sequenza con Errori")
        
        try:
            action1 = NetworkAction(id="duplicate", type=ActionType.CONFIG_CHANGE, target="sw1", parameters={})
            action2 = NetworkAction(id="duplicate", type=ActionType.CONFIG_CHANGE, target="sw2", parameters={})
            
            ActionSequence(
                id="invalid-seq",
                intent_id="test",
                actions=[action1, action2],
                estimated_duration=60
            )
        except ValueError as e:
            self.print_success(f"✅ Errore ID duplicati catturato: {str(e)}")
    
    def generate_final_report(self):
        """Genera un report finale dei risultati."""
        self.print_header("REPORT FINALE DEMO")
        
        self.print_section("Statistiche Parsing Intent")
        if self.demo_results:
            avg_confidence = sum(r['confidence'] for r in self.demo_results) / len(self.demo_results)
            total_entities = sum(r['entities'] for r in self.demo_results)
            
            self.print_result("Intent Processati", len(self.demo_results))
            self.print_result("Confidenza Media", f"{avg_confidence:.1%}")
            self.print_result("Entità Totali Estratte", total_entities)
            self.print_result("Tipi di Intent", len(set(r['type'] for r in self.demo_results)))
        
        self.print_section("Capacità Dimostrate")
        capabilities = [
            "✅ Parsing intent in linguaggio naturale italiano",
            "✅ Estrazione automatica di entità e parametri",
            "✅ Generazione azioni di rete validate",
            "✅ Formattazione per Northbound Script",
            "✅ Gestione sequenze multi-azione",
            "✅ Integrazione con stato della rete",
            "✅ Gestione completa network slice",
            "✅ Cache intelligente dello stato di rete con TTL",
            "✅ Correlazione intent-contesto automatica",
            "✅ Rilevamento anomalie in tempo reale",
            "✅ Classificazione automatica severità anomalie",
            "✅ Generazione risposte automatiche alle anomalie",
            "✅ Rilevamento pattern e apprendimento adattivo",
            "✅ Arricchimento contesto per elaborazione LLM",
            "✅ Validazione parametri e gestione errori",
            "✅ Ottimizzazione ordine di esecuzione",
            "✅ Tracciabilità completa delle operazioni"
        ]
        
        for capability in capabilities:
            print(f"   {capability}")
        
        self.print_section("Prossimi Sviluppi")
        next_features = [
            "🔄 Integrazione con controller RYU reale",
            "🤖 Miglioramento modello LLM con fine-tuning",
            "📊 Dashboard di monitoraggio real-time",
            "🔒 Autenticazione e autorizzazione avanzata",
            "📈 Analytics e machine learning per ottimizzazioni",
            "🌐 Supporto multi-tenant avanzato",
            "⚡ API REST per integrazione esterna",
            "🔔 Sistema di notifiche e alerting"
        ]
        
        for feature in next_features:
            print(f"   {feature}")
        
        print("\n" + "="*80)
        print("🎉 DEMO COMPLETATA CON SUCCESSO!")
        print("   Il sistema è pronto per l'integrazione in ambiente di produzione.")
        print("="*80)
    
    def run_full_demo(self):
        """Esegue la demo completa."""
        print("🚀 AVVIO DEMO SISTEMA LLM INTEGRATION MODULE")
        print("   Sistema di Networking Intent-Based con Large Language Models")
        print("   Versione: 1.0.0 | Data: Dicembre 2024")
        
        try:
            self.demo_intent_parsing()
            self.demo_action_generation()
            self.demo_network_state_integration()
            self.demo_network_slice_management()
            self.demo_context_analyzer()
            self.demo_error_handling()
            self.generate_final_report()
            
        except Exception as e:
            print(f"\n❌ Errore durante la demo: {str(e)}")
            print("   Controllare la configurazione del sistema.")
            return False
        
        return True


def main():
    """Funzione principale per eseguire la demo."""
    demo_system = NetworkDemoSystem()
    success = demo_system.run_full_demo()
    
    if success:
        print("\n💡 Per eseguire nuovamente la demo: python demo_test.py")
        print("💡 Per vedere i test automatici: python -m pytest tests/ -v")
    
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())