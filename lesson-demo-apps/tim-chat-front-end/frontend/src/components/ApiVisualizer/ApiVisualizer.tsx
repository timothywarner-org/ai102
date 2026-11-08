import React from 'react';
import { Stack, Text, StackItem, DefaultButton, IStackStyles, ProgressIndicator } from '@fluentui/react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { nord } from 'react-syntax-highlighter/dist/esm/styles/prism';

import { ChatMessage } from '../../api/models';
import styles from './ApiVisualizer.module.css';

interface ApiVisualizerProps {
  request: {
    messages: ChatMessage[];
    timestamp: number;
  };
  response?: {
    answer: string;
    latency: number;
    tokens?: {
      prompt: number;
      completion: number;
      total: number;
    };
  };
  onClose: () => void;
}

const stackStyles: IStackStyles = {
  root: {
    backgroundColor: '#f8f9fa',
    padding: '20px',
    borderRadius: '8px',
    boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
    maxWidth: '800px',
    margin: '20px auto'
  }
};

export const ApiVisualizer: React.FC<ApiVisualizerProps> = ({ request, response, onClose }) => {
  if (!response?.tokens) return null;

  const { prompt, completion, total } = response.tokens;
  const promptPercentage = (prompt / total) * 100;
  const completionPercentage = (completion / total) * 100;

  return (
    <Stack styles={stackStyles}>
      <Stack horizontal horizontalAlign="space-between" verticalAlign="center">
        <Text variant="xLarge" className={styles.title}>Token Usage Analysis</Text>
        <DefaultButton onClick={onClose} text="Close" />
      </Stack>
      
      <StackItem className={styles.section}>
        <Stack horizontal horizontalAlign="space-between" className={styles.tokenSummary}>
          <Stack className={styles.tokenMetric}>
            <Text variant="large" className={styles.tokenCount}>{prompt}</Text>
            <Text>Prompt Tokens</Text>
          </Stack>
          <Stack className={styles.tokenMetric}>
            <Text variant="large" className={styles.tokenCount}>{completion}</Text>
            <Text>Completion Tokens</Text>
          </Stack>
          <Stack className={styles.tokenMetric}>
            <Text variant="large" className={styles.tokenCount}>{total}</Text>
            <Text>Total Tokens</Text>
          </Stack>
        </Stack>

        <div className={styles.tokenVisualization}>
          <div className={styles.tokenBar}>
            <div 
              className={styles.promptBar} 
              style={{ width: `${promptPercentage}%` }}
              title={`Prompt Tokens: ${prompt} (${promptPercentage.toFixed(1)}%)`}
            />
            <div 
              className={styles.completionBar}
              style={{ width: `${completionPercentage}%` }}
              title={`Completion Tokens: ${completion} (${completionPercentage.toFixed(1)}%)`}
            />
          </div>
          <div className={styles.tokenBarLabels}>
            <Text>Prompt</Text>
            <Text>Completion</Text>
          </div>
        </div>

        <Stack className={styles.tokenDetails}>
          <Text variant="medium">Response Time: {response.latency}ms</Text>
          <Text variant="medium">Average Tokens/Second: {((total / response.latency) * 1000).toFixed(2)}</Text>
        </Stack>
      </StackItem>
    </Stack>
  );
}; 