import React, { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import { 
  Code, 
  Bug, 
  Bot, 
  GitPullRequest, 
  CheckCircle, 
  XCircle, 
  Rocket,
  Server,
  Activity,
  Database,
  FileText,
  MessageSquare,
  Briefcase
} from 'lucide-react';

const icons = {
  github: Code,
  bug: Bug,
  bot: Bot,
  pr: GitPullRequest,
  approve: CheckCircle,
  reject: XCircle,
  rocket: Rocket,
  server: Server,
  activity: Activity,
  db: Database,
  notion: FileText,
  slack: MessageSquare,
  jira: Briefcase
};

export const CustomNode = memo(({ data, isConnectable }) => {
  const IconComponent = icons[data.icon] || Bot;
  
  let className = "custom-node";
  if (data.status === 'active') className += " active";
  if (data.status === 'error') className += " error";
  if (data.status === 'success') className += " success";

  return (
    <div className={className}>
      {data.badge && (
        <div className={`node-badge ${data.badgeColor || 'warning'}`}>
          {data.badge}
        </div>
      )}
      <Handle type="target" position={Position.Top} isConnectable={isConnectable} />
      
      <div className="icon">
        <IconComponent size={28} />
      </div>
      <div className="title">{data.label}</div>
      <div className="status-text">{data.subline || "Idle"}</div>
      
      <Handle type="source" position={Position.Bottom} isConnectable={isConnectable} />
    </div>
  );
});
