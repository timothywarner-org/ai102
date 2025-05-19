import React, { useState } from 'react';
import { Stack, Text, PrimaryButton, Dropdown, IDropdownOption, TextField, IStackStyles } from '@fluentui/react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { nord } from 'react-syntax-highlighter/dist/esm/styles/prism';

import styles from './CodePlayground.module.css';

interface CodePlaygroundProps {
  initialCode?: string;
  language?: string;
  onExecute?: (code: string) => Promise<string>;
}

const supportedLanguages: IDropdownOption[] = [
  { key: 'javascript', text: 'JavaScript' },
  { key: 'python', text: 'Python' },
  { key: 'typescript', text: 'TypeScript' },
  { key: 'sql', text: 'SQL' }
];

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

export const CodePlayground: React.FC<CodePlaygroundProps> = ({
  initialCode = '',
  language = 'javascript',
  onExecute
}) => {
  const [code, setCode] = useState(initialCode);
  const [selectedLanguage, setSelectedLanguage] = useState(language);
  const [output, setOutput] = useState('');
  const [isExecuting, setIsExecuting] = useState(false);
  const [error, setError] = useState('');

  const handleLanguageChange = (_event: React.FormEvent<HTMLDivElement>, option?: IDropdownOption) => {
    if (option) {
      setSelectedLanguage(option.key as string);
    }
  };

  const handleCodeChange = (_event: React.FormEvent<HTMLTextAreaElement | HTMLInputElement>, newValue?: string) => {
    setCode(newValue || '');
  };

  const handleExecute = async () => {
    if (!onExecute) return;

    setIsExecuting(true);
    setError('');
    
    try {
      const result = await onExecute(code);
      setOutput(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setIsExecuting(false);
    }
  };

  return (
    <Stack styles={stackStyles}>
      <Stack horizontal horizontalAlign="space-between" verticalAlign="center">
        <Text variant="xLarge" className={styles.title}>Code Playground</Text>
        <Dropdown
          selectedKey={selectedLanguage}
          options={supportedLanguages}
          onChange={handleLanguageChange}
          styles={{ root: { width: 200 } }}
        />
      </Stack>

      <Stack className={styles.section}>
        <Text variant="large">Code</Text>
        <TextField
          multiline
          rows={10}
          value={code}
          onChange={handleCodeChange}
          className={styles.codeInput}
          spellCheck={false}
        />
      </Stack>

      <Stack horizontal horizontalAlign="space-between" verticalAlign="center">
        <PrimaryButton
          text="Execute"
          onClick={handleExecute}
          disabled={isExecuting || !code.trim()}
        />
        {isExecuting && <Text>Executing...</Text>}
      </Stack>

      {(output || error) && (
        <Stack className={styles.section}>
          <Text variant="large">Output</Text>
          <SyntaxHighlighter
            language={selectedLanguage}
            style={nord}
            className={error ? styles.error : ''}>
            {error || output}
          </SyntaxHighlighter>
        </Stack>
      )}
    </Stack>
  );
}; 