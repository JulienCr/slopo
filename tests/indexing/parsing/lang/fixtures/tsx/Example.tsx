function Greeting(props: { name: string }): JSX.Element {
  return <div>Hello, {props.name}!</div>;
}

const Counter = (): JSX.Element => {
  return <span>0</span>;
};

function double(n: number): number {
  return n * 2;
}

class Widget {
  render(): JSX.Element {
    return <b>widget</b>;
  }
}
