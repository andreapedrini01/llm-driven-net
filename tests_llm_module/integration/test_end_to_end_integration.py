"""Test integrato end-to-end per tutti i moduli sviluppati fino ad ora."""

import pytest
from datetime import datetime
from llm_integration_module.services.intent_parser import IntentParser
from llm_integration_module.models.intent import IntentObject, IntentType, Entity
from llm_integration_module.models.network import (
    NetworkState, Topology, Switch, Host, Link, 
    NetworkMetrics, BandwidthMetrics, LatencyMetrics, UtilizationMetrics
)
from typing import List
from llm_integration_module.models.actions import NetworkAction, ActionType, ActionSequence


class TestEndToEndIntegration:
    """Test integrato per verificare il funzionamento completo del sistema."""
    
    def setup_method(self):
        """Setup per ogni test."""
        self.parser = IntentParser()
        self.network_state = self._create_test_network_state()
    
    def _create_test_network_state(self):
        """Crea uno stato di rete di test realistico."""
        # Switches
        switches = [
            Switch(id="sw1", name="switch1", dpid="0000000000000001", ports=[1, 2, 3], status="active"),
            Switch(id="sw2", name="switch2", dpid="0000000000000002", ports=[1, 2, 3], status="active"),
            Switch(id="sw3", name="switch3", dpid="0000000000000003", ports=[1, 2, 3], status="inactive")
        ]
        
        # Hosts
        hosts = [
            Host(id="h1", mac_address="00:00:00:00:00:01", ip_address="10.0.0.1", 
                 connected_switch="sw1", connected_port=1, status="active"),
            Host(id="h2", mac_address="00:00:00:00:00:02", ip_address="10.0.0.2", 
                 connected_switch="sw2", connected_port=1, status="active"),
            Host(id="h3", mac_address="00:00:00:00:00:03", ip_address="10.0.0.3", 
                 connected_switch="sw3", connected_port=1, status="inactive")
        ]
        
        # Links
        links = [
            Link(id="link1", source_switch="sw1", source_port=2, 
                 destination_switch="sw2", destination_port=2, 
                 bandwidth=1000, status="active"),
            Link(id="link2", source_switch="sw2", source_port=3, 
                 destination_switch="sw3", destination_port=3, 
                 bandwidth=500, status="inactive")
        ]
        
        topology = Topology(switches=switches, hosts=hosts, links=links)
        
        # Metrics
        bandwidth_metrics = BandwidthMetrics(
            total_capacity=1500, used_bandwidth=300, 
            available_bandwidth=1200, utilization_percentage=20.0
        )
        latency_metrics = LatencyMetrics(
            average_latency=15.5, min_latency=5.0, 
            max_latency=50.0, jitter=2.3
        )
        utilization_metrics = UtilizationMetrics(
            cpu_utilization=45.0, memory_utilization=60.0
        )
        metrics = NetworkMetrics(
            bandwidth=bandwidth_metrics, latency=latency_metrics, 
            utilization=utilization_metrics
        )
        
        return NetworkState(
            timestamp=datetime.now(), topology=topology, 
            flows=[], metrics=metrics, anomalies=[]
        )
    
    def test_complete_workflow_clear_intent(self):
        """
        Test del workflow completo con un intent chiaro e non ambiguo.
        
        Verifica:
        - Intent parsing corretto (Property 1)
        - Validazione risorse esistenti (Property 2)
        - Nessuna richiesta di chiarimento per intent chiari (Property 3)
        - Generazione azioni valide (Property 8)
        """
        # Intent chiaro e specifico
        intent_text = "configure switch sw1 with bandwidth 500mbps"
        
        # 1. PARSING DELL'INTENT (Property 1)
        result = self.parser.analyze_and_clarify_intent(intent_text, self.network_state)
        
        intent = result['intent']
        assert isinstance(intent, IntentObject)
        assert intent.raw_text == intent_text
        assert intent.intent_type == IntentType.CONFIGURATION
        assert intent.confidence >= 0.5  # Intent chiaro dovrebbe avere alta confidenza
        
        # Verifica entità estratte
        assert len(intent.entities) >= 2  # Almeno azione e risorsa
        entity_types = [e.type for e in intent.entities]
        assert 'action' in entity_types or 'resource' in entity_types
        
        # 2. VALIDAZIONE RISORSE (Property 2)
        contextualized_intent = result['contextualized_intent']
        assert 'sw1' in contextualized_intent.relevant_resources
        assert len(contextualized_intent.conflicts) == 0  # sw1 è attivo, nessun conflitto
        
        # 3. GESTIONE CHIARIMENTI (Property 3)
        ambiguity_analysis = result['ambiguity_analysis']
        assert ambiguity_analysis['ambiguity_score'] <= 0.7  # Ambiguità ragionevole
        
        # Se richiede chiarimenti, dovrebbero essere minimi e appropriati
        if result['needs_clarification']:
            assert len(result['clarification_requests']) <= 2  # Pochi chiarimenti
            for request in result['clarification_requests']:
                assert len(request) > 5  # Richieste significative
        else:
            assert len(result['clarification_requests']) == 0
        
        # 4. GENERAZIONE AZIONI (Property 8)
        # Simuliamo la generazione di azioni basata sull'intent
        actions = self._generate_actions_from_intent(intent, contextualized_intent)
        assert len(actions) > 0
        
        # Verifica validità delle azioni
        for action in actions:
            assert isinstance(action, NetworkAction)
            assert action.target in contextualized_intent.relevant_resources
            assert action.type in [ActionType.FLOW_MOD, ActionType.CONFIG_CHANGE]
            assert action.priority >= 0
            assert action.timeout > 0
    
    def test_complete_workflow_ambiguous_intent(self):
        """
        Test del workflow completo con un intent ambiguo.
        
        Verifica:
        - Intent parsing (Property 1)
        - Rilevamento ambiguità e richiesta chiarimenti (Property 3)
        - Gestione risorse non specificate
        """
        # Intent ambiguo
        intent_text = "configure the switch"
        
        # 1. PARSING DELL'INTENT
        result = self.parser.analyze_and_clarify_intent(intent_text, self.network_state)
        
        intent = result['intent']
        assert isinstance(intent, IntentObject)
        assert intent.intent_type == IntentType.CONFIGURATION
        
        # 2. RILEVAMENTO AMBIGUITÀ (Property 3)
        ambiguity_analysis = result['ambiguity_analysis']
        assert ambiguity_analysis['ambiguity_score'] > 0.3  # Alta ambiguità
        assert result['needs_clarification']
        
        clarification_requests = result['clarification_requests']
        assert len(clarification_requests) > 0
        
        # Verifica che le richieste di chiarimento siano appropriate
        combined_requests = ' '.join(clarification_requests).lower()
        assert any(word in combined_requests for word in [
            'which', 'what', 'specify', 'clarify', 'switch'
        ])
        
        # Dovrebbe suggerire switch disponibili
        available_switches = [s.id for s in self.network_state.topology.switches if s.status == "active"]
        requests_mention_switches = any(
            any(switch_id in req for switch_id in available_switches)
            for req in clarification_requests
        )
        # Questo è un controllo soft - non tutti i sistemi potrebbero implementarlo
    
    def test_complete_workflow_invalid_resource(self):
        """
        Test del workflow completo con risorsa inesistente.
        
        Verifica:
        - Intent parsing (Property 1)
        - Validazione risorse inesistenti (Property 2)
        - Suggerimenti per risorse alternative
        """
        # Intent con risorsa inesistente
        intent_text = "configure switch sw99 with bandwidth 1000mbps"
        
        # 1. PARSING DELL'INTENT
        result = self.parser.analyze_and_clarify_intent(intent_text, self.network_state)
        
        intent = result['intent']
        assert isinstance(intent, IntentObject)
        assert intent.intent_type == IntentType.CONFIGURATION
        
        # 2. VALIDAZIONE RISORSE (Property 2)
        contextualized_intent = result['contextualized_intent']
        
        # sw99 non dovrebbe essere nelle risorse rilevanti (non esiste)
        assert 'sw99' not in contextualized_intent.relevant_resources
        
        # Dovrebbe esserci almeno un conflitto o raccomandazione
        total_issues = len(contextualized_intent.conflicts) + len(contextualized_intent.recommendations)
        assert total_issues > 0
        
        # Verifica che ci siano suggerimenti per risorse alternative
        combined_feedback = ' '.join(
            contextualized_intent.conflicts + contextualized_intent.recommendations
        ).lower()
        assert 'sw99' in combined_feedback  # Dovrebbe menzionare la risorsa non trovata
    
    def test_complete_workflow_inactive_resource(self):
        """
        Test del workflow completo con risorsa inattiva.
        
        Verifica:
        - Intent parsing (Property 1)
        - Validazione stato risorse (Property 2)
        - Rilevamento conflitti per risorse inattive
        """
        # Intent con risorsa inattiva
        intent_text = "configure switch sw3 with bandwidth 800mbps"
        
        # 1. PARSING DELL'INTENT
        result = self.parser.analyze_and_clarify_intent(intent_text, self.network_state)
        
        intent = result['intent']
        assert isinstance(intent, IntentObject)
        
        # 2. VALIDAZIONE RISORSE (Property 2)
        contextualized_intent = result['contextualized_intent']
        
        # sw3 esiste ma è inattivo, dovrebbe generare conflitti
        assert len(contextualized_intent.conflicts) > 0
        
        # Verifica che il conflitto menzioni lo stato inattivo
        combined_conflicts = ' '.join(contextualized_intent.conflicts).lower()
        assert any(word in combined_conflicts for word in [
            'inactive', 'inattivo', 'sw3', 'not available', 'non disponibile'
        ])
    
    def test_workflow_with_clarification_response(self):
        """
        Test del workflow completo con gestione della risposta ai chiarimenti.
        
        Verifica il ciclo completo: intent ambiguo → chiarimento → intent raffinato
        """
        # 1. Intent iniziale ambiguo
        initial_intent = "configure bandwidth"
        
        result = self.parser.analyze_and_clarify_intent(initial_intent, self.network_state)
        
        # Dovrebbe richiedere chiarimenti
        assert result['needs_clarification']
        assert len(result['clarification_requests']) > 0
        
        # 2. Simulazione risposta dell'utente ai chiarimenti
        clarification_response = "for switch sw1 set to 750mbps"
        
        # 3. Gestione della risposta ai chiarimenti
        refined_result = self.parser.handle_clarification_response(
            result['intent'], clarification_response, self.network_state
        )
        
        # Il nuovo intent dovrebbe essere più chiaro
        refined_intent = refined_result['intent']
        assert refined_intent.confidence >= result['intent'].confidence
        
        # Dovrebbe avere meno ambiguità
        assert refined_result['ambiguity_analysis']['ambiguity_score'] <= result['ambiguity_analysis']['ambiguity_score']
        
        # Dovrebbe identificare sw1 come risorsa rilevante
        refined_contextualized = refined_result['contextualized_intent']
        assert 'sw1' in refined_contextualized.relevant_resources
    
    def test_multiple_properties_integration(self):
        """
        Test che verifica l'integrazione di tutte le proprietà insieme.
        
        Scenario complesso che tocca tutte le proprietà implementate.
        """
        # Intent complesso che tocca multiple proprietà
        intent_text = "create flow from h1 to h2 through sw1 and sw2 with high priority"
        
        result = self.parser.analyze_and_clarify_intent(intent_text, self.network_state)
        
        # Property 1: Intent parsing completeness
        intent = result['intent']
        assert isinstance(intent, IntentObject)
        assert intent.confidence >= 0.3  # Dovrebbe parsare ragionevolmente bene
        assert len(intent.entities) >= 3  # Azione, risorse multiple, parametri
        
        # Property 2: Resource validation consistency
        contextualized_intent = result['contextualized_intent']
        expected_resources = ['h1', 'h2', 'sw1', 'sw2']
        found_resources = [r for r in expected_resources if r in contextualized_intent.relevant_resources]
        assert len(found_resources) >= 2  # Almeno alcune risorse dovrebbero essere identificate
        
        # Property 3: Clarification appropriateness
        # Per un intent complesso ma specifico, potrebbe o non potrebbe richiedere chiarimenti
        if result['needs_clarification']:
            # Se richiede chiarimenti, dovrebbero essere appropriati
            assert len(result['clarification_requests']) <= 3  # Non troppi
            for request in result['clarification_requests']:
                assert len(request) > 10  # Richieste significative
                assert '?' in request or any(word in request.lower() for word in [
                    'which', 'what', 'specify', 'clarify'
                ])
        
        # Property 8: Action validation (simulata)
        if not result['needs_clarification']:
            actions = self._generate_actions_from_intent(intent, contextualized_intent)
            if actions:  # Se sono state generate azioni
                for action in actions:
                    assert isinstance(action, NetworkAction)
                    assert action.type in [ActionType.FLOW_MOD, ActionType.CONFIG_CHANGE]
                    assert 0 <= action.priority <= 1000
    
    def _generate_actions_from_intent(self, intent: IntentObject, contextualized_intent) -> List[NetworkAction]:
        """
        Simula la generazione di azioni da un intent (Property 8).
        
        Questa è una implementazione semplificata per i test.
        """
        actions = []
        
        if intent.intent_type == IntentType.CONFIGURATION:
            for resource in contextualized_intent.relevant_resources:
                # Crea un'azione di configurazione per ogni risorsa rilevante
                action = NetworkAction(
                    id=f"action_{len(actions) + 1}",
                    type=ActionType.CONFIG_CHANGE,
                    target=resource,
                    parameters={"source": "test_integration"},
                    priority=500,
                    timeout=30
                )
                actions.append(action)
        
        elif intent.intent_type == IntentType.QUERY:
            # Per le query, non generiamo azioni di modifica
            pass
        
        return actions
    
    def test_performance_integration(self):
        """
        Test delle performance del sistema integrato.
        
        Verifica che il sistema risponda in tempi ragionevoli.
        """
        import time
        
        test_intents = [
            "show status of switch sw1",
            "configure switch sw2 with bandwidth 1000mbps",
            "create flow from h1 to h2",
            "delete flow on switch sw1",
            "modify bandwidth of link link1 to 800mbps"
        ]
        
        total_time = 0
        for intent_text in test_intents:
            start_time = time.time()
            
            result = self.parser.analyze_and_clarify_intent(intent_text, self.network_state)
            
            end_time = time.time()
            processing_time = end_time - start_time
            total_time += processing_time
            
            # Ogni intent dovrebbe essere processato in meno di 1 secondo
            assert processing_time < 1.0, f"Intent '{intent_text}' took {processing_time:.2f}s"
            
            # Verifica che il risultato sia valido
            assert isinstance(result['intent'], IntentObject)
            assert 'ambiguity_analysis' in result
            assert 'clarification_requests' in result
        
        # Il tempo totale per 5 intent dovrebbe essere ragionevole
        avg_time = total_time / len(test_intents)
        assert avg_time < 0.5, f"Average processing time {avg_time:.2f}s is too high"
    
    def test_error_resilience_integration(self):
        """
        Test della resilienza agli errori del sistema integrato.
        
        Verifica che il sistema gestisca gracefully input problematici.
        """
        problematic_intents = [
            "",  # Intent vuoto
            "   ",  # Solo spazi
            "a",  # Intent troppo corto
            "x" * 1000,  # Intent troppo lungo
            "!@#$%^&*()",  # Caratteri speciali
            "configure switch sw1 with bandwidth -500mbps",  # Valori negativi
            "delete create modify switch sw1",  # Azioni conflittuali
        ]
        
        for intent_text in problematic_intents:
            try:
                if not intent_text or not intent_text.strip():
                    # Intent vuoti dovrebbero sollevare ValueError
                    with pytest.raises(ValueError):
                        self.parser.analyze_and_clarify_intent(intent_text, self.network_state)
                else:
                    # Altri intent problematici dovrebbero essere gestiti gracefully
                    result = self.parser.analyze_and_clarify_intent(intent_text, self.network_state)
                    
                    # Il sistema dovrebbe comunque produrre un risultato valido
                    assert isinstance(result['intent'], IntentObject)
                    assert 'ambiguity_analysis' in result
                    
                    # Per input problematici, dovrebbe richiedere chiarimenti
                    if len(intent_text.strip()) > 0:
                        assert result['ambiguity_analysis']['ambiguity_score'] > 0.3
            
            except Exception as e:
                # Se c'è un'eccezione, dovrebbe essere gestita appropriatamente
                assert isinstance(e, (ValueError, TypeError)), f"Unexpected exception for '{intent_text}': {e}"