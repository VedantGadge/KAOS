import React, { useState, useEffect, useCallback } from 'react';
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  MarkerType,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import axios from 'axios';
import { CustomNode } from './CustomNode';
import { Activity, Bug, Code, Rocket } from 'lucide-react';

const nodeTypes = { custom: CustomNode };

const initialNodes = [
  // Triage Flow
  { id: 'bug', type: 'custom', position: { x: 50, y: 200 }, data: { label: 'Bug', icon: 'bug', status: 'idle', subline: 'Source' } },
  { id: 'kafka_1', type: 'custom', position: { x: 350, y: 200 }, data: { label: 'Kafka', icon: 'server', status: 'idle', subline: 'Queue' } },
  { id: 'triager', type: 'custom', position: { x: 650, y: 200 }, data: { label: 'AI Agent Service', icon: 'bot', status: 'idle', subline: 'Triager' } },
  { id: 'neo4j_1', type: 'custom', position: { x: 950, y: -50 }, data: { label: 'Employee Graph DB', icon: 'db', status: 'idle', subline: 'Find active emp' } },
  { id: 'notion_1', type: 'custom', position: { x: 950, y: 150 }, data: { label: 'Notion', icon: 'notion', status: 'idle', subline: 'Update' } },
  { id: 'slack_1', type: 'custom', position: { x: 950, y: 350 }, data: { label: 'Slack', icon: 'slack', status: 'idle', subline: 'Announce' } },
  { id: 'jira_1', type: 'custom', position: { x: 950, y: 550 }, data: { label: 'Jira', icon: 'jira', status: 'idle', subline: 'Raise ticket' } },

  // Review Flow
  { id: 'github_pr', type: 'custom', position: { x: 50, y: 800 }, data: { label: 'GitHub PR', icon: 'github', status: 'idle', subline: 'Dev pushes PR' } },
  { id: 'reviewer', type: 'custom', position: { x: 650, y: 800 }, data: { label: 'AI Agent Service', icon: 'bot', status: 'idle', subline: 'Reviewer' } },
  { id: 'neo4j_2', type: 'custom', position: { x: 950, y: 800 }, data: { label: 'Employee Graph DB', icon: 'db', status: 'idle', subline: 'Find reviewer' } },
  
  { id: 'reject_flow', type: 'custom', position: { x: 650, y: 1000 }, data: { label: 'Slack', icon: 'slack', status: 'idle', subline: 'DM Reject' } },
  { id: 'notion_reject', type: 'custom', position: { x: 350, y: 1000 }, data: { label: 'Notion', icon: 'notion', status: 'idle', subline: 'Status Update' } },
  
  { id: 'clean_flow', type: 'custom', position: { x: 950, y: 1000 }, data: { label: 'Slack', icon: 'slack', status: 'idle', subline: 'Clean (DM)' } },
  { id: 'kafka_2', type: 'custom', position: { x: 1250, y: 1000 }, data: { label: 'Kafka', icon: 'server', status: 'idle', subline: 'Queue' } },
  { id: 'github_push', type: 'custom', position: { x: 1550, y: 1000 }, data: { label: 'GitHub', icon: 'github', status: 'idle', subline: 'Accept, git pushed' } },

  // Ops Flow
  { id: 'prod', type: 'custom', position: { x: 1550, y: 1200 }, data: { label: 'Prod Env', icon: 'server', status: 'idle', subline: 'Deployment' } },
  { id: 'kafka_3', type: 'custom', position: { x: 1550, y: 1400 }, data: { label: 'Kafka', icon: 'server', status: 'idle', subline: 'Queue' } },
  { id: 'ops', type: 'custom', position: { x: 1550, y: 1600 }, data: { label: 'Agent Service', icon: 'bot', status: 'idle', subline: 'Ops Manager' } },
  
  // Ops Fail
  { id: 'ops_fail', type: 'custom', position: { x: 1150, y: 1600 }, data: { label: 'Fail', icon: 'reject', status: 'error', subline: 'Path' } },
  { id: 'notion_fail', type: 'custom', position: { x: 850, y: 1400 }, data: { label: 'Notion', icon: 'notion', status: 'idle', subline: 'show Notiectarity' } },
  { id: 'db_fail', type: 'custom', position: { x: 850, y: 1600 }, data: { label: 'Database', icon: 'db', status: 'idle', subline: 'Save logs' } },
  { id: 'slack_fail', type: 'custom', position: { x: 850, y: 1800 }, data: { label: 'Slack', icon: 'slack', status: 'idle', subline: 'DM dev & reviewer' } },

  // Ops Success
  { id: 'ops_success', type: 'custom', position: { x: 1950, y: 1600 }, data: { label: 'Success', icon: 'approve', status: 'success', subline: 'Path' } },
  { id: 'notion_success', type: 'custom', position: { x: 2250, y: 1300 }, data: { label: 'Notion', icon: 'notion', status: 'idle', subline: 'Update Status' } },
  { id: 'jira_success', type: 'custom', position: { x: 2250, y: 1500 }, data: { label: 'Jira', icon: 'jira', status: 'idle', subline: 'Close Ticket' } },
  { id: 'db_success', type: 'custom', position: { x: 2250, y: 1700 }, data: { label: 'Database', icon: 'db', status: 'idle', subline: 'Save logs' } },
  { id: 'slack_success', type: 'custom', position: { x: 2250, y: 1900 }, data: { label: 'Slack', icon: 'slack', status: 'idle', subline: 'Announce' } }
];

const initialEdges = [
  // Triage
  { id: 'e-bug-k1', source: 'bug', target: 'kafka_1' },
  { id: 'e-k1-t1', source: 'kafka_1', target: 'triager' },
  { id: 'e-t1-n1', source: 'triager', target: 'neo4j_1' },
  { id: 'e-t1-no1', source: 'triager', target: 'notion_1' },
  { id: 'e-t1-s1', source: 'triager', target: 'slack_1' },
  { id: 'e-t1-j1', source: 'triager', target: 'jira_1' },

  // Review
  { id: 'e-gh-r1', source: 'github_pr', target: 'reviewer' },
  { id: 'e-r1-n2', source: 'reviewer', target: 'neo4j_2' },
  
  { id: 'e-r1-rej', source: 'reviewer', target: 'reject_flow', label: 'Reject / Conflict' },
  { id: 'e-rej-no', source: 'reject_flow', target: 'notion_reject' },

  { id: 'e-r1-cln', source: 'reviewer', target: 'clean_flow', label: 'Clean' },
  { id: 'e-cln-k2', source: 'clean_flow', target: 'kafka_2' },
  { id: 'e-k2-gh2', source: 'kafka_2', target: 'github_push' },

  // Ops
  { id: 'e-gh2-prod', source: 'github_push', target: 'prod' },
  { id: 'e-prod-k3', source: 'prod', target: 'kafka_3' },
  { id: 'e-k3-ops', source: 'kafka_3', target: 'ops' },
  
  { id: 'e-ops-fail', source: 'ops', target: 'ops_fail' },
  { id: 'e-of-no', source: 'ops_fail', target: 'notion_fail' },
  { id: 'e-of-db', source: 'ops_fail', target: 'db_fail' },
  { id: 'e-of-sl', source: 'ops_fail', target: 'slack_fail' },

  { id: 'e-ops-succ', source: 'ops', target: 'ops_success' },
  { id: 'e-os-no', source: 'ops_success', target: 'notion_success' },
  { id: 'e-os-ji', source: 'ops_success', target: 'jira_success' },
  { id: 'e-os-db', source: 'ops_success', target: 'db_success' },
  { id: 'e-os-sl', source: 'ops_success', target: 'slack_success' },
];

function App() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [logs, setLogs] = useState([]);
  const [backendOnline, setBackendOnline] = useState(false);

  useEffect(() => {
    const fetchEvents = async () => {
      try {
        const res = await axios.get('/api/events');
        setBackendOnline(true);
        const events = res.data.events || [];
        
        let updatedNodes = [...initialNodes];
        let updatedEdges = [...initialEdges];
        
        if (events.length > 0) {
          const latestEvent = events[events.length - 1];
          const type = latestEvent.type;
          
          const highlightNode = (id, status, subline, badge = null, badgeColor = null) => {
            updatedNodes = updatedNodes.map(n => 
              n.id === id ? { ...n, data: { ...n.data, status, subline, badge, badgeColor } } : n
            );
          };
          const animateEdge = (source, target) => {
            updatedEdges = updatedEdges.map(e => 
              (e.source === source && e.target === target) 
                ? { ...e, animated: true, style: { stroke: '#3b82f6', strokeWidth: 3 } } 
                : e
            );
          };

          // Sequential animation logic for Triage
          if (type === "SENTRY_TRIGGER" || type === "QUALITY_REPORT") {
            highlightNode('bug', 'active', 'Sent Event');
            animateEdge('bug', 'kafka_1');
            highlightNode('kafka_1', 'active', 'Queued');
            animateEdge('kafka_1', 'triager');
            highlightNode('triager', 'active', 'Analyzing');
            
            // Artificial delay to show Neo4j first, then others
            // In a real app we'd have precise event timestamps, here we mock the sequence if recent
            const timeSinceEvent = Date.now() / 1000 - latestEvent.timestamp;
            
            if (timeSinceEvent > 1) {
              animateEdge('triager', 'neo4j_1');
              highlightNode('neo4j_1', 'success', 'Found active: Bob');
            }
            if (timeSinceEvent > 2) {
              animateEdge('triager', 'notion_1');
              highlightNode('notion_1', 'active', 'Updating', 'Needs Attention', 'error');
              animateEdge('triager', 'slack_1');
              highlightNode('slack_1', 'success', 'Announced');
              animateEdge('triager', 'jira_1');
              highlightNode('jira_1', 'success', 'Created TKT-101');
            }
          }
          
          if (type === "GITHUB_TRIGGER" || type === "PR_OPENED" || type === "PR_UPDATED") {
            highlightNode('github_pr', 'active', 'Pushed');
            animateEdge('github_pr', 'reviewer');
            highlightNode('reviewer', 'active', 'Reviewing');
            animateEdge('reviewer', 'neo4j_2');
            highlightNode('neo4j_2', 'success', 'Found: Dave');
          }

          if (type === "REVIEW_SUBMITTED") {
             const payload = latestEvent.payload;
             const decision = payload.decision || (payload.review && payload.review.state);
             if (decision === 'CHANGES_REQUESTED') {
                 highlightNode('reviewer', 'error', 'Rejected');
                 animateEdge('reviewer', 'reject_flow');
                 highlightNode('reject_flow', 'active', 'DM sent');
                 animateEdge('reject_flow', 'notion_reject');
                 highlightNode('notion_reject', 'active', 'Updating', 'Status: Needs Attention', 'error');
             } else {
                 highlightNode('reviewer', 'success', 'Approved');
                 animateEdge('reviewer', 'clean_flow');
                 highlightNode('clean_flow', 'success', 'Clean');
                 animateEdge('clean_flow', 'kafka_2');
                 highlightNode('kafka_2', 'active', 'Queue');
                 animateEdge('kafka_2', 'github_push');
                 highlightNode('github_push', 'success', 'Merged');
             }
          }

          if (type === "JENKINS_TRIGGER" || type === "DEPLOY_STATUS") {
            highlightNode('prod', 'active', 'Deploying');
            animateEdge('prod', 'kafka_3');
            highlightNode('kafka_3', 'active', 'Ops queue');
            animateEdge('kafka_3', 'ops');
            highlightNode('ops', 'active', 'Running');
            
            const status = latestEvent.payload.status;
            if (status === 'SUCCEEDED' || status === 'success') {
                animateEdge('ops', 'ops_success');
                highlightNode('ops_success', 'success', 'Deployed!');
                animateEdge('ops_success', 'notion_success');
                highlightNode('notion_success', 'success', 'Done', 'Status: Resolved', 'success');
                animateEdge('ops_success', 'jira_success');
                highlightNode('jira_success', 'success', 'Closed');
                animateEdge('ops_success', 'db_success');
                highlightNode('db_success', 'success', 'Saved');
                animateEdge('ops_success', 'slack_success');
                highlightNode('slack_success', 'success', 'Notified');
            }
            if (status === 'FAILED' || status === 'failure') {
                animateEdge('ops', 'ops_fail');
                highlightNode('ops_fail', 'error', 'Failed!');
                animateEdge('ops_fail', 'notion_fail');
                highlightNode('notion_fail', 'error', 'Error', 'Status: Blocked', 'error');
                animateEdge('ops_fail', 'db_fail');
                highlightNode('db_fail', 'success', 'Saved logs');
                animateEdge('ops_fail', 'slack_fail');
                highlightNode('slack_fail', 'active', 'DM sent');
            }
          }
        }
        
        setNodes(updatedNodes);
        setEdges(updatedEdges);
      } catch (err) {
        setBackendOnline(false);
      }
    };

    const intervalId = setInterval(fetchEvents, 1000);
    return () => clearInterval(intervalId);
  }, [setNodes, setEdges]);

  const triggerSimulation = async (type, option = null) => {
    let payload = { service_name: 'payment-service' };
    if (type === 'sentry_error' || type === 'pr_open') {
        payload.error_message = 'NullPointerException in ProcessTransaction';
        if (type === 'pr_open') payload.pr_author = 'dev_user';
    } else if (type === 'pr_decision') {
        payload.pr_id = 102;
        payload.decision = option;
        payload.comment = option === 'APPROVED' ? 'Looks good' : 'Fix this';
    } else if (type === 'deployment') {
        payload.status = option;
    }
    
    try {
      await axios.post(`/api/simulate/${type}`, payload);
      setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] Triggered ${type}`]);
    } catch (e) {
      setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] Failed ${type}: ${e.message}`]);
    }
  };

  return (
    <div className="app-container">
      <div className="status-indicator">
        <div className={`dot ${backendOnline ? '' : 'offline'}`}></div>
        {backendOnline ? 'System Online' : 'Backend Offline'}
      </div>

      <div className="flow-area">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          fitView
          minZoom={0.2}
          className="react-flow-dark"
        >
          <Background color="#334155" gap={16} />
        </ReactFlow>
        
        <div className="logs-panel">
          <div style={{fontWeight: 'bold', marginBottom: '0.5rem', color: '#fff'}}>System Event Log</div>
          {logs.map((log, i) => (
            <div key={i} className="log-entry">{log}</div>
          ))}
          {logs.length === 0 && <div>No events yet. Trigger a simulation to start.</div>}
        </div>
      </div>

      <div className="side-panel">
        <div className="panel-header">
          <h2><Activity size={20} /> KAOS Control</h2>
        </div>
        
        <div className="panel-content" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          
          <div className="card">
            <h3><Bug size={16} /> Simulate Issue</h3>
            <p>Trigger a Sentry exception webhook.</p>
            <button className="btn btn-primary" onClick={() => triggerSimulation('sentry_error')}>Trigger Sentry Error</button>
          </div>

          <div className="card">
            <h3><Code size={16} /> Simulate PR</h3>
            <p>Trigger a GitHub PR webhook.</p>
            <button className="btn btn-primary" onClick={() => triggerSimulation('pr_open')}>Trigger PR Open</button>
            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
              <button className="btn" style={{background: 'var(--success)', color: '#fff', border: 'none'}} onClick={() => triggerSimulation('pr_decision', 'APPROVED')}>Approve</button>
              <button className="btn" style={{background: 'var(--error)', color: '#fff', border: 'none'}} onClick={() => triggerSimulation('pr_decision', 'CHANGES_REQUESTED')}>Reject</button>
            </div>
          </div>

          <div className="card">
            <h3><Rocket size={16} /> Simulate Deploy</h3>
            <p>Trigger CI/CD deployment status.</p>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button className="btn" style={{background: 'var(--success)', color: '#fff', border: 'none'}} onClick={() => triggerSimulation('deployment', 'success')}>Success</button>
              <button className="btn" style={{background: 'var(--error)', color: '#fff', border: 'none'}} onClick={() => triggerSimulation('deployment', 'failure')}>Fail</button>
            </div>
          </div>
          
        </div>
      </div>
    </div>
  );
}

export default App;
