import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import Button from '@components/Button';
import Modal from '@components/Modal';
import Select from '@components/Select';
import type { BatchPlan, ItemPlan } from 'types/pywebview/pywebview-api';

import type { ConflictChoice } from './types';

type ConflictReviewDialogProps = {
  plan: BatchPlan;
  isPending: boolean;
  onCancel: () => void;
  onConfirm: (choices: Readonly<Record<string, ConflictChoice>>) => void;
};

/** Validate native select values without asserting an unchecked string into a conflict action. */
const isChoice = (value: string): value is ConflictChoice =>
  ['skip', 'overwrite', 'rename'].includes(value);

/** Review every existing artifact once, with per-output decisions and coherent shared-stem renaming. */
const ConflictReviewDialog = ({
  onCancel,
  onConfirm,
  plan,
  isPending,
}: ConflictReviewDialogProps) => {
  const { t } = useTranslation();
  const conflicts = plan.items.flatMap((item) =>
    item.outputs.filter((output) => output.action === 'ask'),
  );
  const [choices, setChoices] = useState<Record<string, ConflictChoice>>(() =>
    Object.fromEntries(conflicts.map((output) => [output.id, 'skip'])),
  );
  const [bulk, setBulk] = useState('skip');

  /** Apply one recording decision to every conflicting output in its format set. */
  const choose = (item: ItemPlan, action: ConflictChoice) => {
    setBulk('mixed');
    setChoices((previous) => ({
      ...previous,
      ...Object.fromEntries(
        item.outputs
          .filter((output) => output.action === 'ask')
          .map((output) => [output.id, action]),
      ),
    }));
  };

  return (
    <Modal
      isDismissible={!isPending}
      title={t('batch.conflictTitle', { count: conflicts.length })}
      onClose={onCancel}
    >
      <p className="text-ink/65 mt-3 text-sm leading-6">
        {t('batch.conflictIntro')}
      </p>
      <div className="border-ink/10 mt-5 flex items-center justify-between gap-4 border-y py-3">
        <label className="text-sm font-medium" htmlFor="bulk-conflict">
          {t('batch.applyAll')}
        </label>
        <Select
          className="w-40"
          disabled={isPending}
          id="bulk-conflict"
          value={bulk}
          onChange={(event) => {
            const action = event.target.value;
            if (isChoice(action)) {
              setBulk(action);
              setChoices(
                Object.fromEntries(
                  conflicts.map((output) => [output.id, action]),
                ),
              );
            }
          }}
        >
          <option disabled value="mixed">
            {t('batch.perOutput')}
          </option>
          <option value="skip">{t('batch.skip')}</option>
          <option value="overwrite">{t('batch.overwrite')}</option>
          <option value="rename">{t('batch.rename')}</option>
        </Select>
      </div>
      <div className="my-3 max-h-80 space-y-5 overflow-auto p-2">
        {plan.items
          .filter((item) =>
            item.outputs.some((output) => output.action === 'ask'),
          )
          .map((item) => {
            const outputs = item.outputs.filter(
              (output) => output.action === 'ask',
            );
            return (
              <section key={item.itemId}>
                <div className="mb-3 flex items-center justify-between gap-3">
                  <p
                    className="min-w-0 truncate text-sm font-semibold"
                    title={item.sourcePath}
                  >
                    {item.sourcePath.split(/[\\/]/).pop()}
                  </p>
                  <Select
                    aria-label={t('batch.actionFor', { path: item.sourcePath })}
                    className="w-36 shrink-0"
                    disabled={isPending}
                    value={choices[outputs[0].id]}
                    onChange={(event) => {
                      const action = event.target.value;
                      if (isChoice(action)) {
                        choose(item, action);
                      }
                    }}
                  >
                    <option value="skip">{t('batch.skip')}</option>
                    <option value="overwrite">{t('batch.overwrite')}</option>
                    <option value="rename">{t('batch.rename')}</option>
                  </Select>
                </div>
                <div className="space-y-2">
                  {outputs.map((output) => (
                    <code
                      key={output.id}
                      className="text-ink/65 block text-xs break-all"
                    >
                      {output.path}
                    </code>
                  ))}
                </div>
              </section>
            );
          })}
      </div>
      <p className="text-ink/65 text-xs leading-5">{t('batch.renameHint')}</p>
      <footer className="mt-6 flex items-center justify-between gap-3">
        <span className="text-ink/65 text-xs">
          {t('batch.filesInBatch', { count: plan.items.length })}
        </span>
        <div className="flex gap-2">
          <Button disabled={isPending} onClick={onCancel}>
            {t('common.cancel')}
          </Button>
          <Button
            disabled={isPending}
            icon="arrow-right"
            variant="primary"
            onClick={() => onConfirm(choices)}
          >
            {t(isPending ? 'batch.starting' : 'batch.startBatch')}
          </Button>
        </div>
      </footer>
    </Modal>
  );
};

export default ConflictReviewDialog;
