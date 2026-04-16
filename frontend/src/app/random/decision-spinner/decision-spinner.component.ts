import { Component, input, output, signal, OnDestroy, OnInit } from '@angular/core';
import { Option } from '../../models/option.model';

@Component({
  selector: 'app-decision-spinner',
  imports: [],
  templateUrl: './decision-spinner.component.html',
  styleUrl: './decision-spinner.component.scss',
})
export class DecisionSpinnerComponent implements OnInit, OnDestroy {
  options = input.required<Option[]>();
  winnerSelected = output<Option>();

  highlightIndex = signal(-1);
  isFinished = signal(false);

  private timeoutIds: ReturnType<typeof setTimeout>[] = [];

  ngOnInit(): void {
    this.startSpin();
  }

  ngOnDestroy(): void {
    for (const id of this.timeoutIds) {
      clearTimeout(id);
    }
  }

  private startSpin(): void {
    const opts = this.options();
    if (opts.length === 0) return;

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const winnerIdx = Math.floor(Math.random() * opts.length);

    if (prefersReducedMotion) {
      this.highlightIndex.set(winnerIdx);
      this.isFinished.set(true);
      this.winnerSelected.emit(opts[winnerIdx]);
      return;
    }

    // Build delay schedule: exponential deceleration
    const schedule: number[] = [];
    let delay = 60;
    while (delay < 800) {
      schedule.push(delay);
      delay = Math.round(delay * 1.12);
    }
    schedule.push(800, 1000);

    const totalSteps = schedule.length;
    // Calculate start so we land on winnerIdx after totalSteps
    const startIdx = ((winnerIdx - (totalSteps % opts.length)) % opts.length + opts.length) % opts.length;
    let currentIdx = startIdx;

    let stepNum = 0;
    const tick = (): void => {
      this.highlightIndex.set(currentIdx % opts.length);
      stepNum++;
      if (stepNum >= totalSteps) {
        this.isFinished.set(true);
        this.winnerSelected.emit(opts[winnerIdx]);
        return;
      }
      currentIdx++;
      const id = setTimeout(tick, schedule[stepNum]);
      this.timeoutIds.push(id);
    };

    const id = setTimeout(tick, schedule[0]);
    this.timeoutIds.push(id);
  }
}
