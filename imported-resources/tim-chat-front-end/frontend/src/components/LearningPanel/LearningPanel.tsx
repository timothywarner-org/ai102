import React, { useEffect } from 'react';
import { Stack, Text, Link, IStackStyles, FontIcon } from '@fluentui/react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { nord } from 'react-syntax-highlighter/dist/esm/styles/prism';

import { useLearningPanelStore } from '../../state/LearningPanelState';
import styles from './LearningPanel.module.css';

const stackStyles: IStackStyles = {
  root: {
    backgroundColor: '#f8f9fa',
    padding: '20px',
    borderRadius: '8px',
    boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
    width: '100%',
    height: '100%',
    overflowY: 'auto'
  }
};

const getIconName = (type: 'documentation' | 'tutorial' | 'example' | 'fun_fact' | 'investigation_tip' | 'learning_path' | 'api_request' | 'api_response') => {
  switch (type) {
    case 'documentation':
      return 'Documentation';
    case 'tutorial':
      return 'Education';
    case 'example':
      return 'Code';
    case 'fun_fact':
      return 'LightBulb';
    case 'investigation_tip':
      return 'Search';
    case 'learning_path':
      return 'NavigateForward';
    case 'api_request':
      return 'Send';
    case 'api_response':
      return 'ReceiveAnswer';
    default:
      return 'Link';
  }
};

export const LearningPanel: React.FC = () => {
  const { topic, resources, examples, enrichments, isFirstLoad, setIsFirstLoad } = useLearningPanelStore();

  // Show welcome message only on first load
  if (isFirstLoad) {
    return (
      <Stack styles={stackStyles} className={styles.emptyState}>
        <Text variant="xLarge">Learning Panel</Text>
        <Text>Watch token usage and costs as you chat with Azure OpenAI</Text>
      </Stack>
    );
  }

  if (!topic) {
    return (
      <Stack styles={stackStyles} className={styles.emptyState}>
        <Text variant="xLarge">Learning Panel</Text>
        <Text>Ask a question to see token usage and insights</Text>
      </Stack>
    );
  }

  // Group enrichments by type for better organization
  const tokenEnrichments = enrichments.filter(e => e.type === 'learning_path' && e.title.includes('Token'));
  const otherEnrichments = enrichments.filter(e => 
    !(e.type === 'learning_path' && e.title.includes('Token'))
  );

  return (
    <Stack styles={stackStyles}>
      {/* Token Usage Section */}
      {tokenEnrichments.length > 0 && (
        <Stack className={styles.section}>
          {tokenEnrichments.map((enrichment, index) => (
            <Stack key={index} className={styles.enrichmentItem}>
              <Text variant="large" className={styles.enrichmentTitle}>
                {enrichment.title}
              </Text>
              <Text className={styles.enrichmentContent}>{enrichment.content}</Text>
              {enrichment.relatedLinks && (
                <Stack horizontal wrap tokens={{ childrenGap: 8 }} className={styles.enrichmentLinks}>
                  {enrichment.relatedLinks.map((link, i) => (
                    <Link key={i} href={link} target="_blank">Learn more</Link>
                  ))}
                </Stack>
              )}
            </Stack>
          ))}
        </Stack>
      )}

      {/* Other Enrichments Section */}
      {otherEnrichments.length > 0 && (
        <Stack className={styles.section}>
          {otherEnrichments.map((enrichment, index) => (
            <Stack key={index} className={styles.enrichmentItem}>
              <Text variant="large" className={styles.enrichmentTitle}>
                {enrichment.title}
              </Text>
              <Text className={styles.enrichmentContent}>{enrichment.content}</Text>
              {enrichment.relatedLinks && (
                <Stack horizontal wrap tokens={{ childrenGap: 8 }} className={styles.enrichmentLinks}>
                  {enrichment.relatedLinks.map((link, i) => (
                    <Link key={i} href={link} target="_blank">Learn more</Link>
                  ))}
                </Stack>
              )}
            </Stack>
          ))}
        </Stack>
      )}
    </Stack>
  );
};