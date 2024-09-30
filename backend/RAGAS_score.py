from ragas.metrics import (
    answer_relevancy,
    faithfulness,
    context_utilization 
    
)
from datasets import Dataset 
from ragas.metrics import faithfulness
from ragas import evaluate
import os
from dotenv import load_dotenv
load_dotenv()


os.environ["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY")


def ragas_eval(question,answer,contexts):
    data_samples = {
    'question': [question],
    'answer': [answer],
    'contexts' : [[contexts]],
    }
    dataset = Dataset.from_dict(data_samples)
    score = evaluate(dataset,metrics=[faithfulness,answer_relevancy,context_utilization])
    return score

result = ragas_eval("What issues did Amazon's Elastic Block Storage (EBS) service face in 2012 and how did it affect the company?","Amazon's Elastic Block Storage (EBS) service faced downtime in 2012 due to an electric outage at the U.S. East data center in Virginia, the largest and oldest data center causing outage issues. This downtime led to inconvenience and discomfort for customers who regularly used the website. To address this, Amazon needed to perform major upgrades on the U.S. East data center to prevent future service disruptions. Additionally, some of Amazon's services like Kindle and Cloud experienced increased expenditures, prompting plans to reduce investments in these initiatives. Despite these challenges, Amazon aimed to remain competitive by investing in new revenue-generating projects to reflect the company's value.","['�s largest book retailer operating both online and physical\n\nretail businesses, competes intensively with Amazon for the market share in the book industry. It\n\npursues an integrated focused cost leadership/differentiation strategy to target price-sensitive\n\nconsumers by providing books not readily or commonly available at a less expensive price.\n\nThe competitors’ analysis can be summarized as below:\n\n1 Future objectives: Competitors want to compete for a good strategic position and become\n\nthe market leader in both e-commerce and physical commerce.\n\n2 Current strategy: Competitors aim to increase profitability, gain market share, and\n\nprovide a wide variety of products to compete against Amazon through utilizing\n\ncompetitive pricing, cost leadership, and differentiation strategies.\n\n3 Assumptions: Competitors believe that the demand for online shopping will continue to\n\ngrow as consumers seek for more convenient and efficient ways of shopping.\n\n4 Capabilities: Competitors offer similar products as Amazon either at a lower price or\n\naccompanied with differentiated services. Some of them have an international presence\n\nwith stable financial performance, enabling them to form global strategic alliances to\n\nincrease their market base of customers.\n\nCurrent Situations & Challenges\n\nAmazon uses huge amount of data storage to improve customer service. However,\n\nAmazon’s Elastic Block Storage (EBS) service has been down several times in 2012 due to an\n\n6\n\nelectric outage. The main problem comes from the Amazon’s U.S. East data center in Virginia,\n\nwhich is the biggest and the oldest data center that has been causing outage issues. The company\n\nneeds to do major upgrades on the U.S. East data center to prevent the services from going down\n\nin the future. Otherwise, the server crashes can bring inconvenience and discomfort to the\n\ncustomers who use the website regularly.\n\nSome of Amazon’s services such as Kindle and Cloud have been increasing expenditures\n\nthroughout the company. Amazon is planning to reduce investments in the Kindle and Cloud\n\ninitiatives next year. In order to remain competitive in the industry, Amazon should keep\n\ninvesting in new projects that generate more revenue to reflect the value of the company.\n\nWhile Amazon’s main interest is in long-term investments, such as video content and\n\ndistribution centers, it is difficult to predict when the benefits from these investments will be realized.\n\nAmazon has stopped growing for a while and their margin has been constant for several years. The\n\ncompany needs a margin expansion in order to prevent the company’s share price from dropping.\n\nFuture Outlook\n\nOverall, there are remarkable challenges for Amazon to yet overcome. If they are able to\n\nswiftly react they will be able to maintain their competitive advantages through harnessing their\n\ncore competencies. Continued success in the emerging markets will ensure that Amazon has a\n\nbright and better tomorrow.\n\n7']")
print(result)
print(type(result))