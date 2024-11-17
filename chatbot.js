const { GPTx } = require("@ruingl/gptx");
const gptx = new GPTx({
    provider: 'Nextway',
    model: 'gpt-4o-free'
});

const main = async () => {
    const conversation = process.argv[2]; // Nhận toàn bộ ngữ cảnh từ command line argument
    const messages = [{ role: 'user', content: conversation }];

    const response = await gptx.ChatCompletion(messages);
    console.log(response);
};

main();

